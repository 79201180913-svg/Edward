from __future__ import annotations

from typing import Any

from edward.api.accounts import AccountsApi
from edward.services.account_context import AccountContext


class AccountService:
    """Application service for account discovery, lifecycle and selection."""

    def __init__(self, api: AccountsApi, context: AccountContext | None = None) -> None:
        self._api = api
        self._context = context or AccountContext()

    @property
    def context(self) -> AccountContext:
        return self._context

    def get_accounts(self) -> Any:
        return self._api.get_accounts()

    def get_open_accounts(self) -> list[Any]:
        response = self.get_accounts()
        source = response.accounts if hasattr(response, "accounts") else response.get("accounts", [])
        return [account for account in source if self.is_open(account)]

    def create_sandbox_account(self, name: str | None = None) -> Any:
        response = self._api.open_sandbox_account(name)
        account_id = self._field(response, "account_id")
        if account_id:
            self._context.set_active_id(str(account_id))
        return response

    def close_sandbox_account(self, account_id: str) -> Any:
        account_id = str(account_id).strip()
        if not account_id:
            raise ValueError("account_id cannot be empty")
        response = self._api.close_sandbox_account(account_id)
        if self._context.active_account_id == account_id:
            self._context.clear()
        return response

    def select_active_account(self, account_id: str) -> Any:
        account = self.select_account(self.get_accounts(), account_id)
        if not self.is_open(account):
            raise ValueError("Only open accounts can be active")
        self._context.set_active(account)
        return account

    def get_selected_account_id(self) -> str | None:
        return self._context.active_account_id

    @staticmethod
    def is_open(account: Any) -> bool:
        status = str(AccountService._field(account, "status", "")).upper().strip()
        return status in {"OPEN", "ACCOUNT_STATUS_OPEN", "2"} or status.endswith("_OPEN")

    @staticmethod
    def select_account(accounts: Any, account_id: str) -> Any:
        source = accounts.accounts if hasattr(accounts, "accounts") else accounts
        if isinstance(accounts, dict):
            source = accounts.get("accounts", [])
        target = str(account_id).strip()
        for account in source:
            if str(AccountService._field(account, "id", "")).strip() == target:
                return account
        raise ValueError(f"Account not found: {target}")

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)
