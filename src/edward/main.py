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
        raise RuntimeError("T-Invest runtime is not configured. Run run_edward.bat to create .venv-tinvest.")
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
    status = account.get("status", "")
    normalized = str(status).upper().strip()
    return normalized in {
        "OPEN",
        "ACCOUNT_STATUS_OPEN",
        "2",
    }


def _request_and_save_token(store: TokenStore) -> str:
    token = request_and_save_token(store)
    if not token:
        print("T-Invest API token entry was cancelled.", file=sys.stderr)
        raise SystemExit(1)
    return token


def _money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _print_financials(client: TInvestAdapterClient, account_id: str) -> None:
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
    print(f"Money positions: {len(balance_service.get_money_positions(positions_response))}")
    print(f"Security positions: {len(balance_service.get_security_positions(positions_response))}")


def _account_label(account: dict) -> str:
    return f"{account.get('id', '')}: {account.get('name', '')} [{account.get('status', '')}]"


def _print_accounts(accounts: list[dict], active_id: str | None) -> None:
    print()
    print("OPEN ACCOUNTS")
    print("----------------------------------------")
    open_accounts = [account for account in accounts if _is_open(account)]
    for index, account in enumerate(open_accounts, start=1):
        marker = " *" if str(account.get("id", "")) == active_id else ""
        print(f"{index}. {_account_label(account)}{marker}")
    if not open_accounts:
        print("No open accounts found.")
    print("----------------------------------------")


def _choose_account(accounts: list[dict], prompt: str) -> dict | None:
    if not accounts:
        print("No open accounts available.")
        return None
    value = input(prompt).strip()
    try:
        index = int(value) - 1
    except ValueError:
        print("Invalid account number.")
        return None
    if not 0 <= index < len(accounts):
        print("Invalid account number.")
        return None
    return accounts[index]


def _account_management(client: TInvestAdapterClient, environment: Environment, accounts: list[dict]) -> tuple[list[dict], str | None]:
    open_accounts = [a for a in accounts if _is_open(a)]
    active_id = str(open_accounts[0].get("id")) if open_accounts else None

    while True:
        accounts = list(client.get_accounts().get("accounts", []))
        open_accounts = [a for a in accounts if _is_open(a)]
        if active_id and not any(str(a.get("id")) == active_id for a in open_accounts):
            active_id = str(open_accounts[0].get("id")) if open_accounts else None

        _print_accounts(accounts, active_id)
        print("1. Show accounts")
        print("2. Switch active account")
        print("3. Show active account financials")
        if environment is Environment.SANDBOX:
            print("4. Create sandbox account")
            print("5. Close sandbox account")
        print("0. Exit")

        choice = input("Select action: ").strip()
        if choice == "0":
            return accounts, active_id
        if choice == "1":
            continue
        if choice == "2":
            selected = _choose_account(open_accounts, "Open account number: ")
            if selected:
                active_id = str(selected.get("id", ""))
                print(f"Active account: {active_id}")
            continue
        if choice == "3":
            if not active_id:
                print("No active account selected.")
            else:
                _print_financials(client, active_id)
            continue
        if choice == "4" and environment is Environment.SANDBOX:
            name = input("Account name (optional): ").strip() or None
            response = client.create_sandbox_account(name)
            new_id = str(response.get("account_id", ""))
            print(f"Sandbox account created: {new_id}")
            active_id = new_id
            continue
        if choice == "5" and environment is Environment.SANDBOX:
            selected = _choose_account(open_accounts, "Open account number to close: ")
            if not selected:
                continue
            account_id = str(selected.get("id", ""))
            confirmation = input(f"Close account {account_id}? [y/N]: ").strip().lower()
            if confirmation != "y":
                print("Cancelled.")
                continue
            client.close_sandbox_account(account_id)
            print(f"Sandbox account closed: {account_id}")
            if active_id == account_id:
                active_id = None
            continue
        print("Unknown action.")


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
        accounts = list(client.get_accounts().get("accounts", []))
        print(f"Accounts found: {len(accounts)}")
        for account in accounts:
            print(f"- {_account_label(account)}")
        if not any(_is_open(account) for account in accounts) and environment is Environment.PRODUCTION:
            print("No open accounts found.")
            return
        _account_management(client, environment, accounts)
    except (EOFError, KeyboardInterrupt):
        print()
        print("Edward stopped by user.")
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
