from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import uuid
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from edward.security.token_store import TokenStore
from tests.e2e import test_sandbox_end_to_end as e2e

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PYTHON = Path(os.getenv("EDWARD_TINVEST_PYTHON", str(ROOT / ".venv-tinvest" / "Scripts" / "python.exe")))
ADAPTER_SCRIPT = ROOT / "runtime" / "tinvest_adapter_combined_fixed.py"
START_TIMEOUT = float(os.getenv("EDWARD_E2E_START_TIMEOUT", "20"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def protective_adapter():
    """Start and stop a fresh Sandbox adapter for each protective-order scenario."""
    previous_url = e2e.ADAPTER_URL
    token = TokenStore().get()
    if not token:
        pytest.skip("No locally stored T-Invest token available")

    port = _free_port()
    e2e.ADAPTER_URL = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["EDWARD_TINVEST_TOKEN"] = token
    env["EDWARD_TINVEST_ENV"] = "sandbox"
    env["EDWARD_TINVEST_PORT"] = str(port)

    process = subprocess.Popen(
        [str(ADAPTER_PYTHON), str(ADAPTER_SCRIPT)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            e2e.ADAPTER_URL = previous_url
            raise RuntimeError(f"Sandbox adapter exited before becoming ready:\n{output}")
        try:
            if e2e._request("GET", "/health").get("status") == "ok":
                break
        except Exception:
            pass
        time.sleep(0.25)
    else:
        output = process.stdout.read() if process.stdout else ""
        process.kill()
        process.wait(timeout=5)
        e2e.ADAPTER_URL = previous_url
        raise RuntimeError(f"Sandbox adapter did not become ready:\n{output}")

    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        e2e.ADAPTER_URL = previous_url


def _request_stop(path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{e2e.ADAPTER_URL}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Stop-order HTTP {exc.code} {path}: {raw}") from exc


def _position_in_account(account_id: str) -> tuple[str, int, Decimal]:
    positions = e2e._request("POST", "/accounts/sandbox-positions", {"account_id": account_id})
    for item in e2e._items(positions, "securities"):
        balance = int(abs(e2e._number(item.get("balance", 0))))
        uid = str(item.get("instrument_uid") or item.get("uid") or "")
        if uid and balance > 0:
            prices = e2e._request("POST", "/market/last-prices", {"instrument_ids": [uid]})
            prices_items = e2e._items(prices, "last_prices")
            if prices_items:
                price = e2e._number(prices_items[0].get("price", 0))
                if price > 0:
                    return uid, balance, price
    pytest.skip("Sandbox account has no position suitable for protective-order E2E")


def _get_price_step(instrument_uid: str) -> Decimal:
    instruments = e2e._request(
        "POST",
        "/instruments/list",
        {"instrument_kind": "SHARE", "api_trade_available_flag": False},
    )
    for item in e2e._items(instruments, "instruments"):
        uid = str(item.get("instrument_uid") or item.get("uid") or item.get("instrument_id") or "")
        if uid != instrument_uid:
            continue
        step = e2e._number(item.get("min_price_increment"))
        if step > 0:
            return step
    return Decimal("0.0001")


def _create_stop(
    account_id: str,
    uid: str,
    side: str,
    kind: str,
    quantity: int,
    stop_price: Decimal,
    price: Decimal | None = None,
) -> dict:
    effective_price = price if price is not None else stop_price
    payload = {
        "account_id": account_id,
        "instrument_uid": uid,
        "instrument_id": uid,
        "direction": side,
        "quantity": quantity,
        "stop_price": str(stop_price),
        "price": str(effective_price),
        "stop_order_type": kind,
        "expiration_type": "STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL",
        "exchange_order_type": "EXCHANGE_ORDER_TYPE_LIMIT" if kind.endswith("STOP_LIMIT") else "EXCHANGE_ORDER_TYPE_MARKET",
        "take_profit_type": "TAKE_PROFIT_TYPE_REGULAR" if kind.endswith("TAKE_PROFIT") else "TAKE_PROFIT_TYPE_UNSPECIFIED",
        "price_type": "PRICE_TYPE_CURRENCY",
        "order_id": str(uuid.uuid4()),
    }
    return _request_stop("/stop-orders/create", payload)


def _list_stops(account_id: str) -> list[dict]:
    response = _request_stop("/stop-orders", {"account_id": account_id})
    return e2e._items(response, "stop_orders")


def _cancel_stop(account_id: str, stop_order_id: str) -> dict:
    return _request_stop("/stop-orders/cancel", {"account_id": account_id, "stop_order_id": stop_order_id})


@pytest.mark.parametrize(
    "kind, stop_multiplier, side",
    [
        ("STOP_ORDER_TYPE_STOP_LOSS", Decimal("0.99"), "STOP_ORDER_DIRECTION_SELL"),
        ("STOP_ORDER_TYPE_TAKE_PROFIT", Decimal("1.01"), "STOP_ORDER_DIRECTION_SELL"),
    ],
)
def test_sandbox_protective_order_create_get_cancel(kind, stop_multiplier, side, protective_adapter):
    if os.getenv("EDWARD_E2E_TRADING", "0") != "1":
        pytest.skip("Protective-order E2E requires EDWARD_E2E_TRADING=1")

    account_id = e2e._get_account_id()
    uid, _balance, current = _position_in_account(account_id)
    step = _get_price_step(uid)
    stop_price = e2e._align_price(current * stop_multiplier, step)
    execution_price = e2e._align_price(current, step)
    assert stop_price > 0
    assert execution_price > 0

    created = _create_stop(account_id, uid, side, kind, 1, stop_price, price=execution_price)
    stop_id = str(created.get("stop_order_id") or "")
    assert stop_id, f"Sandbox did not return stop_order_id: {created}"

    try:
        active = _list_stops(account_id)
        matching = [item for item in active if str(item.get("stop_order_id") or "") == stop_id]
        assert matching, f"Created stop order is missing from GetSandboxStopOrders: {active}"
    finally:
        _cancel_stop(account_id, stop_id)

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        active = _list_stops(account_id)
        if not any(str(item.get("stop_order_id") or "") == stop_id for item in active):
            return
        time.sleep(0.5)
    pytest.fail("Cancelled protective order remained in active stop-order list")


def test_sandbox_stop_limit_create_get_cancel(protective_adapter):
    if os.getenv("EDWARD_E2E_TRADING", "0") != "1":
        pytest.skip("Protective-order E2E requires EDWARD_E2E_TRADING=1")

    account_id = e2e._get_account_id()
    uid, _balance, current = _position_in_account(account_id)
    step = _get_price_step(uid)
    stop_price = e2e._align_price(current * Decimal("0.99"), step)
    limit_price = e2e._align_price(current * Decimal("0.98"), step)
    assert stop_price > 0 and limit_price > 0
    assert limit_price < stop_price

    created = _create_stop(
        account_id,
        uid,
        "STOP_ORDER_DIRECTION_SELL",
        "STOP_ORDER_TYPE_STOP_LIMIT",
        1,
        stop_price,
        price=limit_price,
    )
    stop_id = str(created.get("stop_order_id") or "")
    assert stop_id, f"Sandbox did not return stop_order_id: {created}"

    try:
        active = _list_stops(account_id)
        matching = [item for item in active if str(item.get("stop_order_id") or "") == stop_id]
        assert matching, f"Created stop-limit is missing from GetSandboxStopOrders: {active}"
    finally:
        _cancel_stop(account_id, stop_id)
