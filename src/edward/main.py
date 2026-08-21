from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.config.settings import Environment, Settings
from edward.security.token_store import TokenStore
from edward.services.account_context import AccountContext
from edward.services.account_service import AccountService
from edward.services.balance_service import BalanceService
from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.ui.instrument_catalog import show_catalog
from edward.ui.token_dialog import request_and_save_token
from edward.validation.trading_validator import TradingValidator


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _start_adapter(token: str, environment: Environment) -> subprocess.Popen[bytes]:
    root = _project_root()
    python_exe = root / ".venv-tinvest" / "Scripts" / "python.exe"
    adapter_script = root / "runtime" / "tinvest_adapter.py"
    if not python_exe.exists():
        raise RuntimeError("T-Invest runtime is not configured. Run run_edward.bat to create .venv-tinvest.")
    if not adapter_script.exists():
        raise RuntimeError("T-Invest adapter script is missing: runtime/tinvest_adapter.py")
    env = os.environ.copy()
    env["EDWARD_TINVEST_TOKEN"] = token
    env["EDWARD_TINVEST_ENV"] = environment.value
    env["EDWARD_TINVEST_PORT"] = "8765"
    print(f"[ADAPTER] Starting T-Invest adapter: {adapter_script}")
    print(f"[ADAPTER] Environment: {environment.value.upper()}")
    # Do not hide adapter stdout/stderr. run_edward_gui is the diagnostic console,
    # so SDK and sandbox balance/order logs must remain visible to the user.
    return subprocess.Popen(
        [str(python_exe), str(adapter_script)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=None,
        stderr=None,
    )


def _wait_for_adapter(client: TInvestAdapterClient, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 15.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("T-Invest adapter stopped during startup")
        try:
            client.health()
            print("[ADAPTER] T-Invest adapter is ready")
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"T-Invest adapter did not become ready: {last_error}")


def _request_and_save_token(store: TokenStore) -> str:
    token = request_and_save_token(store)
    if not token:
        print("T-Invest API token entry was cancelled.", file=sys.stderr)
        raise SystemExit(1)
    return token


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _items(response: Any, *names: str) -> list[Any]:
    if isinstance(response, list):
        return response
    for name in names:
        value = _field(response, name)
        if value is not None:
            return list(value)
    return []


def _money(value: Decimal | Any) -> str:
    return f"{Decimal(str(value)):,.2f}".replace(",", " ")


def _account_label(account: Any) -> str:
    return f"{_field(account, 'id', '')}: {_field(account, 'name', '')} [{_field(account, 'status', '')}]"


def _print_accounts(accounts: list[Any], context: AccountContext) -> None:
    print("\nACCOUNTS")
    print("----------------------------------------")
    if not accounts:
        print("No accounts found.")
    for index, account in enumerate(accounts, start=1):
        marker = " *" if str(_field(account, "id", "")) == context.active_account_id else ""
        print(f"{index}. {_account_label(account)}{marker}")
    print("----------------------------------------")
