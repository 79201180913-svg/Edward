from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_URL = os.getenv("EDWARD_E2E_ADAPTER_URL", "http://127.0.0.1:8765")
ADAPTER_PYTHON = Path(
    os.getenv(
        "EDWARD_TINVEST_PYTHON",
        str(ROOT / ".venv-tinvest" / "Scripts" / "python.exe"),
    )
)
ADAPTER_SCRIPT = ROOT / "runtime" / "tinvest_adapter_fixed.py"
START_TIMEOUT = float(os.getenv("EDWARD_E2E_START_TIMEOUT", "20"))


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{ADAPTER_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _adapter_is_ready() -> bool:
    try:
        return _request("GET", "/health").get("status") == "ok"
    except (OSError, HTTPError, URLError, ValueError):
        return False


@pytest.fixture(scope="session")
def sandbox_adapter():
    """Start the real Edward T-Invest adapter against T-Invest Sandbox."""
    if os.getenv("EDWARD_TINVEST_ENV", "sandbox").lower() != "sandbox":
        pytest.fail("E2E tests must run with EDWARD_TINVEST_ENV=sandbox")
    if not os.getenv("EDWARD_TINVEST_TOKEN", "").strip():
        pytest.skip("EDWARD_TINVEST_TOKEN is not configured")
    if not ADAPTER_PYTHON.exists():
        pytest.fail(f"T-Invest Python runtime not found: {ADAPTER_PYTHON}")
    if not ADAPTER_SCRIPT.exists():
        pytest.fail(f"Adapter script not found: {ADAPTER_SCRIPT}")

    if _adapter_is_ready():
        yield None
        return

    env = os.environ.copy()
    env["EDWARD_TINVEST_ENV"] = "sandbox"
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


def test_sandbox_read_only_end_to_end(sandbox_adapter):
    health = _request("GET", "/health")
    assert health["status"] == "ok"
    assert health["environment"] == "sandbox"

    accounts = _request("POST", "/accounts")
    account_items = accounts.get("accounts", [])
    assert account_items, "Sandbox must return at least one account"
    account_id = str(account_items[0]["id"])

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
    instrument_items = instruments.get("instruments", [])
    assert instrument_items, "Sandbox must return SHARE instruments"

    instrument = next(
        (
            item
            for item in instrument_items
            if item.get("instrument_uid") or item.get("uid")
        ),
        None,
    )
    assert instrument is not None, "Instrument response must contain an instrument UID"
    instrument_uid = str(instrument.get("instrument_uid") or instrument.get("uid"))

    prices = _request("POST", "/market/last-prices", {"instrument_ids": [instrument_uid]})
    assert "last_prices" in prices

    statuses = _request("POST", "/market/trading-statuses", {"instrument_ids": [instrument_uid]})
    assert "trading_statuses" in statuses

    orders = _request("POST", "/orders", {"account_id": account_id})
    assert "orders" in orders

    operations = _request("POST", "/operations", {"account_id": account_id, "limit": 10})
    assert "items" in operations or "operations" in operations


@pytest.mark.skipif(
    os.getenv("EDWARD_E2E_TRADING", "0") != "1",
    reason="Trading E2E requires explicit EDWARD_E2E_TRADING=1 confirmation",
)
def test_sandbox_order_lifecycle_is_explicitly_enabled(sandbox_adapter):
    """Reserved for the explicit Sandbox trading confirmation phase.

    This test is intentionally not enabled by the normal E2E run. Once enabled,
    the concrete order scenario must be selected from current Sandbox state
    rather than hard-coded against a potentially unavailable instrument.
    """
    pytest.fail(
        "Sandbox trading E2E is explicitly enabled but the concrete order scenario "
        "has not been approved for this run"
    )
