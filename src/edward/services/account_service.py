from __future__ import annotations

from typing import Any

from edward.api.accounts import AccountsApi


class AccountService:
    """Application service for account discovery, lifecycle and selection."""

    def __init__(self, api: AccountsApi) -> None:
        self._api = api
        self._selected_account_id: str | None = None

    def get_accounts(self) -> Any:
        return self._api.get_accounts()

    def get_open_accounts(self) -> list[Any]:
        response = self.get_accounts()
        source = response.accounts if hasattr(response, "accounts") else response.get("accounts", [])
        return [
            account
            for account in source
            if str(self._field(account, "status", "")).endswith("ACCOUNT_STATUS_OPEN")
        ]

    def create_sandbox_account(self, name: str | None = None) -> Any:
        response = self._api.open_sandbox_account(name)
        account_id = self._field(response, "account_id")
        if account_id:
            self._selected_account_id = str(account_id)
        return response

    def close_sandbox_account(self, account_id: str) -> Any:
        account_id = str(account_id).strip()
        if not account_id:
            raise ValueError("account_id cannot be empty")
        response = self._api.close_sandbox_account(account_id)
        if self._selected_account_id == account_id:
            self._selected_account_id = None
        return response

    def select_account(self, account_id: str) -> Any:
        accounts = self.get_accounts()
        account = self.select_account_from(accounts, account_id)
        self._selected_account_id = str(self._field(account, "id"))
        return account

    def get_selected_account_id(self) -> str | None:
        return self._selected_account_id

    @staticmethod
    def select_account_from(accounts: Any, account_id: str) -> Any:
        source = accounts.accounts if hasattr(accounts, "accounts") else accounts
        if isinstance(accounts, dict):
            source = accounts.get("accounts", [])
        for account in source:
            if AccountService._field(account, "id") == account_id:
                return account
        raise ValueError(f"Account not found: {account_id}")

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)
