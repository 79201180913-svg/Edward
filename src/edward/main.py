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
    return subprocess.Popen([str(python_exe), str(adapter_script)], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


def _choose_account(accounts: list[Any]) -> Any | None:
    if not accounts:
        print("No open accounts available.")
        return None
    try:
        index = int(input("Open account number: ").strip()) - 1
    except ValueError:
        print("Invalid account number.")
        return None
    if not 0 <= index < len(accounts):
        print("Invalid account number.")
        return None
    return accounts[index]


def _print_financials(client: TInvestAdapterClient, context: AccountContext) -> None:
    account_id = context.require_account_id()
    balance = BalanceService(client)
    positions = balance.get_positions(account_id)
    portfolio = balance.get_portfolio(account_id)
    summary = balance.build_summary(positions, portfolio)
    print("\nFINANCIALS")
    print("----------------------------------------")
    print(f"Account:           {account_id}")
    print(f"Currency:          {summary.currency}")
    print(f"Available:         {_money(summary.available)}")
    print(f"Blocked:           {_money(summary.blocked)}")
    print(f"Cash:              {_money(summary.cash)}")
    print(f"Securities:        {_money(summary.securities)}")
    print(f"Portfolio value:   {_money(summary.portfolio_value)}")
    print("----------------------------------------")


def _search_instruments(client: TInvestAdapterClient) -> None:
    query = input("Instrument / ticker / name: ").strip()
    if not query:
        return
    instruments = _items(client.find_instrument(query, True), "instruments")
    print("\nINSTRUMENTS")
    print("----------------------------------------")
    if not instruments:
        print("No instruments found.")
        return
    for index, instrument in enumerate(instruments[:20], start=1):
        print(f"{index}. {_field(instrument, 'ticker', '')} | {_field(instrument, 'name', '')} | uid={_field(instrument, 'uid', _field(instrument, 'instrument_uid', ''))} | trade={_field(instrument, 'api_trade_available_flag', '')}")


def _show_positions(client: TInvestAdapterClient, context: AccountContext) -> None:
    account_id = context.require_account_id()
    securities = _items(client.get_positions(account_id), "securities")
    print("\nPORTFOLIO POSITIONS")
    print("----------------------------------------")
    if not securities:
        print("No security positions.")
        return
    for position in securities:
        print(f"{_field(position, 'ticker', _field(position, 'instrument_uid', ''))}: balance={_field(position, 'balance', '')}, blocked={_field(position, 'blocked', '')}, yield={_field(position, 'expected_yield', '')}")


def _create_order(client: TInvestAdapterClient, context: AccountContext) -> None:
    account_id = context.require_account_id()
    query = input("Instrument / ticker / name: ").strip()
    if not query:
        return
    found = _items(client.find_instrument(query, True), "instruments")
    if not found:
        print("Instrument not found or not available for trading.")
        return
    for index, instrument in enumerate(found[:10], start=1):
        print(f"{index}. {_field(instrument, 'ticker', '')} — {_field(instrument, 'name', '')} — {_field(instrument, 'uid', _field(instrument, 'instrument_uid', ''))}")
    try:
        instrument = found[int(input("Instrument number: ").strip()) - 1]
    except (ValueError, IndexError):
        print("Invalid instrument.")
        return
    uid = str(_field(instrument, "uid", _field(instrument, "instrument_uid", "")))
    prices = _items(client.get_last_prices([uid]), "last_prices")
    current_price = _field(prices[0], "price") if prices else None
    print(f"Current price: {current_price}")
    side_value = input("Operation (BUY/SELL): ").strip().upper()
    if side_value not in {"BUY", "SELL"}:
        print("Invalid operation.")
        return
    type_value = input("Order type (MARKET/LIMIT): ").strip().upper()
    if type_value not in {"MARKET", "LIMIT"}:
        print("This interactive release supports MARKET and LIMIT.")
        return
    try:
        quantity = int(input("Quantity: ").strip())
    except ValueError:
        print("Quantity must be an integer.")
        return
    price = None
    if type_value == "LIMIT":
        raw_price = input(f"Price [{current_price}]: ").strip() or str(current_price or "0")
        try:
            price = Decimal(raw_price)
        except Exception:
            print("Invalid price.")
            return
    request = OrderRequest(account_id=account_id, instrument_uid=uid, side=OrderSide(side_value), order_type=OrderType(type_value), quantity=quantity, price=price)
    total = (price * quantity) if price is not None else None
    print("\nORDER CONFIRMATION")
    print("----------------------------------------")
    print(f"Account:    {account_id}")
    print(f"Instrument: {_field(instrument, 'ticker', uid)}")
    print(f"Operation:  {side_value}")
    print(f"Type:       {type_value}")
    print(f"Quantity:   {quantity}")
    print(f"Price:      {price if price is not None else current_price}")
    if total is not None:
        print(f"Estimated:  {_money(total)}")
    print("----------------------------------------")
    if input("Confirm order? [y/N]: ").strip().lower() != "y":
        print("Cancelled.")
        return
    result = OrderService(client).create_order(request)
    print(f"Order submitted: {_field(result, 'order_id', _field(result, 'orderId', 'unknown'))}")


def _active_orders(client: TInvestAdapterClient, context: AccountContext) -> None:
    account_id = context.require_account_id()
    orders = _items(client.get_orders(account_id), "orders")
    print("\nACTIVE ORDERS")
    print("----------------------------------------")
    if not orders:
        print("No active orders.")
        return
    for index, order in enumerate(orders, start=1):
        print(f"{index}. {_field(order, 'order_id', '')} | {_field(order, 'direction', '')} | {_field(order, 'quantity', '')} | {_field(order, 'execution_report_status', _field(order, 'status', ''))}")
    choice = input("Order number to cancel, or Enter: ").strip()
    if not choice:
        return
    try:
        order = orders[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid order.")
        return
    order_id = str(_field(order, "order_id", ""))
    if input(f"Cancel {order_id}? [y/N]: ").strip().lower() != "y":
        print("Cancelled.")
        return
    OrderService(client).cancel_order(account_id, order_id)
    print(f"Cancel requested: {order_id}")


def _account_management(client: TInvestAdapterClient, environment: Environment, context: AccountContext) -> None:
    while True:
        accounts = _items(client.get_accounts(), "accounts")
        open_accounts = [account for account in accounts if AccountService.is_open(account)]
        if context.active_account_id and not any(str(_field(a, "id", "")) == context.active_account_id for a in open_accounts):
            context.clear()
        if context.active_account_id is None and open_accounts:
            context.set_active(open_accounts[0])
        _print_accounts(accounts, context)
        print("1. Show accounts")
        print("2. Switch active account")
        print("3. Show active account financials")
        print("4. Show portfolio positions")
        print("5. Search instruments")
        print("6. Create order")
        print("7. Show / cancel active orders")
        if environment is Environment.SANDBOX:
            print("8. Create sandbox account")
            print("9. Close sandbox account")
        print("0. Exit")
        choice = input("Select action: ").strip()
        if choice == "0":
            return
        if choice == "1":
            continue
        if choice == "2":
            selected = _choose_account(open_accounts)
            if selected:
                context.set_active(selected)
                print(f"Active account: {context.active_account_id}")
            continue
        if choice == "3":
            try:
                _print_financials(client, context)
            except Exception as exc:
                print(f"ERROR: {exc}")
            continue
        if choice == "4":
            try:
                _show_positions(client, context)
            except Exception as exc:
                print(f"ERROR: {exc}")
            continue
        if choice == "5":
            _search_instruments(client)
            continue
        if choice == "6":
            try:
                _create_order(client, context)
            except Exception as exc:
                print(f"ERROR: {exc}")
            continue
        if choice == "7":
            try:
                _active_orders(client, context)
            except Exception as exc:
                print(f"ERROR: {exc}")
            continue
        if choice == "8" and environment is Environment.SANDBOX:
            name = input("Account name (optional): ").strip() or None
            response = client.create_sandbox_account(name)
            new_id = str(_field(response, "account_id", ""))
            if new_id:
                context.set_active_id(new_id)
            print(f"Sandbox account created: {new_id}")
            continue
        if choice == "9" and environment is Environment.SANDBOX:
            selected = _choose_account(open_accounts)
            if not selected:
                continue
            account_id = str(_field(selected, "id", ""))
            if input(f"Close account {account_id}? [y/N]: ").strip().lower() != "y":
                print("Cancelled.")
                continue
            client.close_sandbox_account(account_id)
            if context.active_account_id == account_id:
                context.clear()
            print(f"Sandbox account closed: {account_id}")
            continue
        print("Unknown action.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Edward Trading Platform v0.1")
    parser.add_argument("--set-token", action="store_true")
    parser.add_argument("--clear-token", action="store_true")
    parser.add_argument("--production", action="store_true")
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
    context = AccountContext()
    try:
        _wait_for_adapter(client, adapter_process)
        accounts = _items(client.get_accounts(), "accounts")
        print(f"Accounts found: {len(accounts)}")
        for account in accounts:
            print(f"- {_account_label(account)}")
        if environment is Environment.PRODUCTION and not any(AccountService.is_open(account) for account in accounts):
            print("No open accounts found.")
            return
        _account_management(client, environment, context)
    except (EOFError, KeyboardInterrupt):
        print("\nEdward stopped by user.")
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
