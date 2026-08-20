from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ActiveAccount:
    account_id: str
    name: str = ""
    status: str = ""


class AccountContext:
    """Single application-level source of truth for the active account."""

    def __init__(self) -> None:
        self._active: ActiveAccount | None = None

    @property
    def active_account_id(self) -> str | None:
        return self._active.account_id if self._active else None

    @property
    def active_account(self) -> ActiveAccount | None:
        return self._active

    def set_active(self, account: Any) -> ActiveAccount:
        account_id = str(self._field(account, "id", "")).strip()
        if not account_id:
            raise ValueError("Cannot activate account without account_id")
        self._active = ActiveAccount(
            account_id=account_id,
            name=str(self._field(account, "name", "")),
            status=str(self._field(account, "status", "")),
        )
        return self._active

    def set_active_id(self, account_id: str) -> None:
        account_id = str(account_id).strip()
        if not account_id:
            raise ValueError("account_id cannot be empty")
        self._active = ActiveAccount(account_id=account_id)

    def clear(self) -> None:
        self._active = None

    def require_account_id(self) -> str:
        if self._active is None:
            raise RuntimeError("No active trading account selected")
        return self._active.account_id

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)
