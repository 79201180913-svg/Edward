from __future__ import annotations

import os
import sys

from edward.api.client import TInvestClient
from edward.config.settings import Environment, Settings
from edward.api.accounts import AccountsApi
from edward.services.account_service import AccountService


def main() -> int:
    token = os.getenv("TINVEST_API_TOKEN", "").strip()
    if not token:
        print("TINVEST_API_TOKEN is not configured", file=sys.stderr)
        return 2

    settings = Settings(environment=Environment.SANDBOX)
    print("Edward Sandbox smoke test")
    print(f"Environment: {settings.environment}")
    print(f"Endpoint: {settings.api_endpoint}")

    try:
        with TInvestClient(settings, token) as client:
            accounts = AccountService(AccountsApi(client)).get_accounts()
            items = getattr(accounts, "accounts", [])
            print(f"Accounts found: {len(items)}")
            for account in items:
                print(f"- {account.id}: {getattr(account, 'name', '')} [{getattr(account, 'status', '')}]")
    except Exception as exc:
        print(f"Sandbox API check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("Sandbox smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
