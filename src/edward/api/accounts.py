from __future__ import annotations

from typing import Any


class AccountsApi:
    """Adapter for T-Invest account operations."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_accounts(self, status: Any | None = None) -> Any:
        if status is None:
            return self._client.users.get_accounts()
        return self._client.users.get_accounts(status=status)

    def open_sandbox_account(self, name: str | None = None) -> Any:
        request: dict[str, Any] = {}
        if name:
            request["name"] = name
        return self._client.sandbox.open_sandbox_account(**request)

    def close_sandbox_account(self, account_id: str) -> Any:
        return self._client.sandbox.close_sandbox_account(account_id=account_id)
