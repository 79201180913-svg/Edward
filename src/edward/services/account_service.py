from __future__ import annotations

from typing import Any

from edward.api.accounts import AccountsApi


class AccountService:
    """Application service for account discovery and selection."""

    def __init__(self, api: AccountsApi) -> None:
        self._api = api

    def get_accounts(self) -> Any:
        return self._api.get_accounts()

    def get_open_accounts(self) -> Any:
        response = self.get_accounts()
        response.accounts[:] = [
            account
            for account in response.accounts
            if str(account.status).endswith("ACCOUNT_STATUS_OPEN")
        ]
        return response

    @staticmethod
    def select_account(accounts: Any, account_id: str) -> Any:
        for account in accounts.accounts:
            if account.id == account_id:
                return account
        raise ValueError(f"Account not found: {account_id}")
