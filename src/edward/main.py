from __future__ import annotations

import argparse
import getpass
import os

from edward.api.accounts import AccountsApi
from edward.api.client import TInvestClient
from edward.api.portfolio import PortfolioApi
from edward.config.settings import Environment, Settings
from edward.security.token_store import TokenStore
from edward.services.account_service import AccountService
from edward.services.balance_service import BalanceService


def main() -> None:
    parser = argparse.ArgumentParser(description="Edward Trading Platform v0.1")
    parser.add_argument("--set-token", action="store_true", help="Save T-Invest API token in OS credential storage")
    parser.add_argument("--clear-token", action="store_true", help="Delete stored T-Invest API token")
    parser.add_argument("--production", action="store_true", help="Use production environment instead of Sandbox")
    args = parser.parse_args()

    store = TokenStore()

    if args.clear_token:
        store.delete()
        print("T-Invest API token removed from local credential storage.")
        return

    if args.set_token:
        token = getpass.getpass("T-Invest API token: ")
        store.save(token)
        print("T-Invest API token saved to OS credential storage.")
        return

    token = store.get()
    if not token:
        print("T-Invest API token is not configured.")
        print("Run: edward --set-token")
        return

    environment = Environment.PRODUCTION if args.production else Environment.SANDBOX
    settings = Settings(environment=environment)

    print("Edward Trading Platform v0.1")
    print(f"Environment: {environment.value.upper()}")
    print(f"Endpoint: {settings.api_endpoint}")

    with TInvestClient(settings, token) as client:
        account_service = AccountService(AccountsApi(client))
        accounts_response = account_service.get_accounts()
        accounts = list(getattr(accounts_response, "accounts", []))

        print(f"Accounts found: {len(accounts)}")
        for account in accounts:
            print(f"- {account.id}: {account.name} [{account.status}]")

        open_accounts = account_service.get_open_accounts()
        if not open_accounts:
            print("No open accounts found.")
            return

        account = open_accounts[0]
        print(f"Active account: {account.id}")

        portfolio_api = PortfolioApi(client)
        balance_service = BalanceService(portfolio_api)
        positions = balance_service.get_positions(account.id)
        money = balance_service.get_money_positions(positions)
        securities = balance_service.get_security_positions(positions)

        print(f"Money positions: {len(money)}")
        for position in money:
            print(f"- {getattr(position, 'currency', '')}: {getattr(position, 'available', getattr(position, 'balance', ''))}")
        print(f"Security positions: {len(securities)}")


if __name__ == "__main__":
    main()
