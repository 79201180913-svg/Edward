from __future__ import annotations

import base64
import os
import socket
import subprocess
import time
import uuid
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

from edward.security.token_store import TokenStore


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_URL = os.getenv("EDWARD_E2E_ADAPTER_URL", "")
ADAPTER_PYTHON = Path(
    os.getenv(
        "EDWARD_TINVEST_PYTHON",
        str(ROOT / ".venv-tinvest" / "Scripts" / "python.exe"),
    )
)
ADAPTER_SCRIPT = ROOT / "runtime" / "tinvest_adapter_fixed.py"
START_TIMEOUT = float(os.getenv("EDWARD_E2E_START_TIMEOUT", "20"))
ORDER_TIMEOUT = float(os.getenv("EDWARD_E2E_ORDER_TIMEOUT", "30"))


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else __import__("json").dumps(payload).encode("utf-8")
    request = Request(
        f"{ADAPTER_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return __import__("json").loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(f"Adapter HTTP {exc.code} for {method} {path}: {body}") from exc


def _adapter_is_ready() -> bool:
    try:
        return _request("GET", "/health").get("status") == "ok"
    except (OSError, HTTPError, URLError, ValueError, RuntimeError):
        return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _items(payload: dict, *keys: str) -> list[dict]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _number(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, dict):
        units = Decimal(str(value.get("units", 0)))
        nano = Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        return units + nano
    return Decimal(str(value))


def _instrument_uid(item: dict) -> str:
    return str(item.get("instrument_uid") or item.get("instrument_id") or item.get("uid") or "")


def _price_from_item(item: dict) -> Decimal:
    for key in ("price", "last_price", "lastPrice"):
        if key in item:
            return _number(item.get(key))
    return Decimal("0")


def _get_account_id() -> str:
    accounts = _request("POST", "/accounts")
    account_items = _items(accounts, "accounts")
    assert account_items, "Sandbox must return at least one account"
    return str(account_items[0].get("id") or account_items[0].get("account_id"))


def _get_tradable_instrument() -> tuple[str, Decimal]:
    instruments = _request(
        "POST",
        "/instruments/list",
        {"instrument_kind": "SHARE", "api_trade_available_flag": True},
    )
    candidates = _items(instruments, "instruments")
    assert candidates, "Sandbox must return SHARE instruments"

    for item in candidates:
        uid = _instrument_uid(item)
        if not uid:
            continue

        # Contract-level preconditions for a BUY market order.
        # These fields are defined by InstrumentsService.Instrument and
        # GetTradingStatus in the provided invest-contracts-master archive.
        if item.get("api_trade_available_flag") is False:
            continue
        if item.get("buy_available_flag") is False:
            continue
        required_tests = item.get("required_tests")
        if isinstance(required_tests, list) and required_tests:
            continue

        try:
            status_payload = _request(
                "POST", "/market/trading-status", {"instrument_id": uid}
            )
        except Exception:
            continue

        status = str(
            status_payload.get("trading_status")
            or status_payload.get("status")
            or ""
        ).upper()
        if status and not any(
            marker in status for marker in ("NORMAL_TRADING", "OPENING", "CLOSING")
        ):
            continue

        # The contract explicitly exposes whether a MARKET order can be placed.
        if status_payload.get("market_order_available_flag") is False:
            continue

        prices = _request("POST", "/market/last-prices", {"instrument_ids": [uid]})
        price_items = _items(prices, "last_prices")
        price = _price_from_item(price_items[0]) if price_items else Decimal("0")
        if price > 0:
            return uid, price

    pytest.skip("No SHARE with API/buy/market-order availability and a positive market price in Sandbox")


def _wait_terminal(account_id: str, order_id: str) -> dict:
    deadline = time.monotonic() + ORDER_TIMEOUT
    last_state: dict = {}
    while time.monotonic() < deadline:
        last_state = _request(
            "POST",
            "/orders/state",
            {"account_id": account_id, "order_id": order_id},
        )
        status = str(
            last_state.get("execution_report_status")
            or last_state.get("status")
            or last_state.get("state")
            or ""
        ).upper()
        if any(token in status for token in ("FILL", "CANCEL", "REJECT", "FAIL", "INACTIVE")):
            return last_state
        time.sleep(1)
    return last_state


def _create_market_order(account_id: str, instrument_uid: str, side: str) -> dict:
    request_id = str(uuid.uuid4())
    return _request(
        "POST",
        "/orders/create",
        {
            "account_id": account_id,
            "instrument_uid": instrument_uid,
            "instrument_id": instrument_uid,
            "direction": side,
            "order_type": "MARKET",
            "quantity": 1,
            "order_id": request_id,
            "request_id": request_id,
        },
    )


def _cancel_if_active(account_id: str, order_id: str) -> dict:
    return _request(
        "POST",
        "/orders/cancel",
        {"account_id": account_id, "order_id": order_id},
    )


@pytest.fixture(scope="module")
def sandbox_adapter():
    global ADAPTER_URL
    if _adapter_is_ready():
        yield None
        return

    token = TokenStore().get_token()
    if not token:
        pytest.skip("No locally stored T-Invest token available")

    port = _free_port()
    ADAPTER_URL = f"http://127.0.0.1:{port}"
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
            raise RuntimeError(f"Sandbox adapter exited before becoming ready:\n{output}")
        if _adapter_is_ready():
            break
        time.sleep(0.25)
    else:
        output = process.stdout.read() if process.stdout else ""
        process.kill()
        process.wait(timeout=5)
        raise RuntimeError(f"Sandbox adapter did not become ready:\n{output}")

    yield process

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_sandbox_read_only_end_to_end(sandbox_adapter):
    health = _request("GET", "/health")
    assert health["status"] == "ok"
    assert health["environment"] == "sandbox"

    account_id = _get_account_id()

    positions = _request("POST", "/accounts/sandbox-positions", {"account_id": account_id})
    assert "money" in positions
    assert "securities" in positions

    portfolio = _request("POST", "/accounts/sandbox-portfolio", {"account_id": account_id})
    assert "total_amount_portfolio" in portfolio
    assert isinstance(portfolio.get("positions", []), list)

    instruments = _request(
        "POST",
        "/instruments/list",
        {"instrument_kind": "SHARE", "api_trade_available_flag": True},
    )
    instrument_items = _items(instruments, "instruments")
    assert instrument_items
    instrument_uid = _instrument_uid(instrument_items[0])
    assert instrument_uid

    prices = _request("POST", "/market/last-prices", {"instrument_ids": [instrument_uid]})
    assert "last_prices" in prices

    statuses = _request("POST", "/market/trading-statuses", {"instrument_ids": [instrument_uid]})
    assert "trading_statuses" in statuses

    orders = _request("POST", "/orders", {"account_id": account_id})
    assert "orders" in orders

    operations = _request("POST", "/operations", {"account_id": account_id, "limit": 10})
    assert "items" in operations or "operations" in operations


def test_sandbox_order_lifecycle_end_to_end(sandbox_adapter):
    """Buy one Sandbox share, observe lifecycle, and unwind it when filled.

    Enable with EDWARD_E2E_TRADING=1. The test never runs against production.
    If the order cannot execute within the timeout, it is cancelled and the
    test records the non-filled terminal state rather than leaving an order open.
    """
    if os.getenv("EDWARD_E2E_TRADING", "0") != "1":
        pytest.skip("Trading E2E requires EDWARD_E2E_TRADING=1")

    account_id = _get_account_id()
    instrument_uid, market_price = _get_tradable_instrument()
    assert market_price > 0

    before_positions = _request(
        "POST", "/accounts/sandbox-positions", {"account_id": account_id}
    )
    before_portfolio = _request(
        "POST", "/accounts/sandbox-portfolio", {"account_id": account_id}
    )

    created = _create_market_order(account_id, instrument_uid, "BUY")
    order_id = str(created.get("order_id") or created.get("id") or "")
    assert order_id, f"Sandbox did not return order_id: {created}"

    state = _wait_terminal(account_id, order_id)
    status = str(
        state.get("execution_report_status")
        or state.get("status")
        or state.get("state")
        or ""
    ).upper()
    lots_executed = int(str(state.get("lots_executed", 0) or 0))
    lots_requested = int(str(state.get("lots_requested", 1) or 1))

    if "FILL" not in status and lots_executed < lots_requested:
        _cancel_if_active(account_id, order_id)
        cancelled = _wait_terminal(account_id, order_id)
        cancelled_status = str(
            cancelled.get("execution_report_status")
            or cancelled.get("status")
            or cancelled.get("state")
            or ""
        ).upper()
        assert any(
            token in cancelled_status
            for token in ("CANCEL", "REJECT", "FAIL", "INACTIVE")
        ), f"Unexpected terminal state after cancellation: {cancelled}"
        return

    assert "FILL" in status or lots_executed >= lots_requested

    after_buy_positions = _request(
        "POST", "/accounts/sandbox-positions", {"account_id": account_id}
    )
    after_buy_portfolio = _request(
        "POST", "/accounts/sandbox-portfolio", {"account_id": account_id}
    )
    assert after_buy_positions != before_positions or after_buy_portfolio != before_portfolio

    sell_created = _create_market_order(account_id, instrument_uid, "SELL")
    sell_order_id = str(sell_created.get("order_id") or sell_created.get("id") or "")
    assert sell_order_id, f"Sandbox did not return SELL order_id: {sell_created}"

    sell_state = _wait_terminal(account_id, sell_order_id)
    sell_status = str(
        sell_state.get("execution_report_status")
        or sell_state.get("status")
        or sell_state.get("state")
        or ""
    ).upper()
    sell_lots_executed = int(str(sell_state.get("lots_executed", 0) or 0))
    sell_lots_requested = int(str(sell_state.get("lots_requested", 1) or 1))

    if "FILL" not in sell_status and sell_lots_executed < sell_lots_requested:
        _cancel_if_active(account_id, sell_order_id)
        cancelled = _wait_terminal(account_id, sell_order_id)
        cancelled_status = str(
            cancelled.get("execution_report_status")
            or cancelled.get("status")
            or cancelled.get("state")
            or ""
        ).upper()
        assert any(
            token in cancelled_status
            for token in ("CANCEL", "REJECT", "FAIL", "INACTIVE")
        ), f"Unexpected SELL terminal state: {cancelled}"
        return

    assert "FILL" in sell_status or sell_lots_executed >= sell_lots_requested
