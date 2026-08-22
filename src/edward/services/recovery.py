from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class RecoverySnapshot:
    accounts: list[Any]
    active_orders: list[Any]
    portfolio: Any
    balance: Any


def recover_state(*, get_accounts: Callable[[], list[Any]], get_orders: Callable[[str], list[Any]], get_portfolio: Callable[[str], Any], get_balance: Callable[[str], Any]) -> RecoverySnapshot:
    accounts = get_accounts()
    if not accounts:
        return RecoverySnapshot([], [], None, None)
    account_id = getattr(accounts[0], "id", None) or (accounts[0].get("id") if isinstance(accounts[0], dict) else None)
    if not account_id:
        raise ValueError("Active account id is missing")
    return RecoverySnapshot(
        accounts=accounts,
        active_orders=get_orders(account_id),
        portfolio=get_portfolio(account_id),
        balance=get_balance(account_id),
    )
