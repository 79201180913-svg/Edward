from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AccountState:
    portfolio: Any
    positions: Any
    balance: Any
    orders: Any


class AccountStateRefreshService:
    """Refreshes all trading state from T-Invest after an order event."""

    def __init__(self, portfolio_service: Any, balance_service: Any, account_service: Any, orders_gateway: Any) -> None:
        self._portfolio = portfolio_service
        self._balance = balance_service
        self._account = account_service
        self._orders = orders_gateway

    def refresh(self, account_id: str) -> AccountState:
        portfolio = self._portfolio.get_portfolio(account_id)
        positions = self._portfolio.get_positions(account_id)
        balance = self._balance.get_balances(account_id)
        orders = self._orders.get_orders(account_id)
        return AccountState(portfolio=portfolio, positions=positions, balance=balance, orders=orders)
