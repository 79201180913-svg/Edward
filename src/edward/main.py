from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.config.settings import Environment, Settings
from edward.security.token_store import TokenStore
from edward.services.balance_service import BalanceService
from edward.ui.token_dialog import request_and_save_token


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _start_adapter(token: str, environment: Environment) -> subprocess.Popen[bytes]:
    root = _project_root()
    python_exe = root / ".venv-tinvest" / "Scripts" / "python.exe"
    adapter_script = root / "runtime" / "tinvest_adapter.py"

    if not python_exe.exists():
        raise RuntimeError(
            "T-Invest runtime is not configured. Run run_edward.bat to create .venv-tinvest."
        )
    if not adapter_script.exists():
        raise RuntimeError("T-Invest adapter script is missing: runtime/tinvest_adapter.py")

    env = os.environ.copy()
    env["EDWARD_TINVEST_TOKEN"] = token
    env["EDWARD_TINVEST_ENV"] = environment.value
    env["EDWARD_TINVEST_PORT"] = "8765"

    return subprocess.Popen(
        [str(python_exe), str(adapter_script)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_adapter(client: TInvestAdapterClient, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 15.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("T-Invest adapter stopped during startup")
        try:
            client.health()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"T-Invest adapter did not become ready: {last_error}")


def _is_open(account: dict) -> bool:
    status = str(account.get("status", "")).upper()
    return status in {"OPEN", "ACCOUNT_STATUS_OPEN"}


def _request_and_save_token(store: TokenStore) -> str:
    token = request_and_save_token(store)
    if not token:
        print("T-Invest API token entry was cancelled.", file=sys.stderr)
        raise SystemExit(1)
    return token


def _money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _print_financials(client: TInvestAdapterClient, account_id: str) -> None:
    """Read and display normalized financial state for the active account."""
    balance_service = BalanceService()
    positions_response = client.get_positions(account_id)
    portfolio_response = client.get_portfolio(account_id)
    summary = balance_service.build_summary(positions_response, portfolio_response)

    print()
    print("FINANCIALS")
    print("----------------------------------------")
    print(f"Currency:          {summary.currency}")
    print(f"Available:         {_money(summary.available)}")
    print(f"Blocked:           {_money(summary.blocked)}")
    print(f"Cash:              {_money(summary.cash)}")
    print(f"Securities:        {_money(summary.securities)}")
    print(f"Portfolio value:   {_money(summary.portfolio_value)}")
    print("----------------------------------------")
    print(
        f"Money positions: {len(balance_service.get_money_positions(positions_response))}"
    )
    print(
        f"Security positions: {len(balance_service.get_security_positions(positions_response))}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Edward Trading Platform v0.1")
    parser.add_argument("--set-token", action="store_true", help="Replace the stored T-Invest API token")
    parser.add_argument("--clear-token", action="store_true", help="Delete stored T-Invest API token")
    parser.add_argument("--production", action="store_true", help="Use production environment instead of Sandbox")
    args = parser.parse_args()

    store = TokenStore()

    if args.clear_token:
        store.delete()
        print("T-Invest API token removed from local credential storage.")
        return

    if args.set_token:
        _request_and_save_token(store)
        return

    token = store.get()
    if not token:
        token = _request_and_save_token(store)

    environment = Environment.PRODUCTION if args.production else Environment.SANDBOX
    settings = Settings(environment=environment)

    print("Edward Trading Platform v0.1")
    print(f"Environment: {environment.value.upper()}")
    print(f"Endpoint: {settings.api_endpoint}")
    print("T-Invest runtime: Python 3.12 adapter")

    adapter_process = _start_adapter(token, environment)
    client = TInvestAdapterClient()

    try:
        _wait_for_adapter(client, adapter_process)

        accounts_response = client.get_accounts()
        accounts = list(accounts_response.get("accounts", []))
        print(f"Accounts found: {len(accounts)}")

        for account in accounts:
            print(
                f"- {account.get('id', '')}: {account.get('name', '')} "
                f"[{account.get('status', '')}]"
            )

        open_accounts = [account for account in accounts if _is_open(account)]
        if not open_accounts:
            print("No open accounts found.")
            return

        account = open_accounts[0]
        account_id = str(account.get("id", ""))
        print(f"Active account: {account_id}")

        _print_financials(client, account_id)

    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        adapter_process.terminate()
        try:
            adapter_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_process.kill()
            adapter_process.wait(timeout=2)


if __name__ == "__main__":
    main()
