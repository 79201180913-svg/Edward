from __future__ import annotations

import json
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
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{ADAPTER_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
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
    return str(item.get("instrument_uid") or item.get("uid") or item.get("figi") or "")


def _price_from_item(item: dict) -> Decimal:
    return _number(item.get("price") or item.get("last_price") or item.get("close_price"))


@pytest.fixture(scope="session")
def sandbox_adapter():
    """Start a dedicated real Edward T-Invest adapter against T-Invest Sandbox.

    The E2E suite uses the same locally stored T-Invest token as the Edward GUI.
    The GUI stores the token in the operating-system credential store via
    TokenStore; the test fixture reads that store and passes the token only to
    the dedicated adapter subprocess through its environment.
    """
    global ADAPTER_URL

    if os.getenv("EDWARD_TINVEST_ENV", "sandbox").lower() != "sandbox":
        pytest.fail("E2E tests must run with EDWARD_TINVEST_ENV=sandbox")

    token = TokenStore().get()
    if not token:
        pytest.skip("T-Invest API token is not configured in Edward local credential storage")

    if not ADAPTER_PYTHON.exists():
        pytest.fail(f"T-Invest Python runtime not found: {ADAPTER_PYTHON}")
    if not ADAPTER_SCRIPT.exists():
        pytest.fail(f"Adapter script not found: {ADAPTER_SCRIPT}")

    external_adapter = bool(ADAPTER_URL)
    if not external_adapter:
        port = _free_port()
        ADAPTER_URL = f"http://127.0.0.1:{port}"
    else:
        if _adapter_is_ready():
            yield None
            return
        pytest.fail(f"Configured E2E adapter is not reachable: {ADAPTER_URL}")

    env = os.environ.copy()
    env["EDWARD_TINVEST_TOKEN"] = token
    env["EDWARD_TINVEST_ENV"] = "sandbox"
    env["EDWARD_TINVEST_PORT"] = str(port)
    process = subprocess.Popen(
        [str(ADAPTER_PYTHON), str(ADAPTER_SCRIPT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if _adapter_is_ready():
            break
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            pytest.fail(f"T-Invest adapter exited during startup:\n{output}")
        time.sleep(0.25)
    else:
        process.terminate()
        output = process.stdout.read() if process.stdout else ""
        pytest.fail(f"T-Invest adapter did not become ready within {START_TIMEOUT}s:\n{output}")

    yield process

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


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
        )
        if status.endswith("TRADING_STATUS_NORMAL_TRADING") or status in {
            "NORMAL_TRADING",
            "SECURITY_TRADING_STATUS_NORMAL_TRADING",
        }:
            prices = _request("POST", "/market/last-prices", {"instrument_ids": [uid]})
            price_items = _items(prices, "last_prices")
            if price_items:
                price = _price_from_item(price_items[0])
                if price > 0:
                    return uid, price

    pytest.skip("No currently tradable SHARE instrument with a positive market price was found")


def _assert_money_shape(value: object) -> None:
    assert isinstance(value, dict), f"Expected money value object, got: {value!r}"
    assert "currency" in value or "units" in value or "nano" in value


# Remaining test cases are intentionally unchanged.
