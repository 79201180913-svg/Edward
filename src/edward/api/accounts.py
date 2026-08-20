from __future__ import annotations

from typing import Any


class AccountsApi:
    """Adapter for T-Invest UsersService account operations."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_accounts(self, status: Any | None = None) -> Any:
        if status is None:
            return self._client.users.get_accounts()
        return self._client.users.get_accounts(status=status)
