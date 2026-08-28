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

    @staticmethod
    def _collection_count(value: Any, *names: str) -> int:
        for name in names:
            if isinstance(value, dict):
                items = value.get(name)
            else:
                items = getattr(value, name, None)
            if items is not None:
                try:
                    return len(items)
                except TypeError:
                    return 0
        return 0

    @staticmethod
    def _collection_keys(value: Any) -> str:
        if isinstance(value, dict):
            return ",".join(sorted(str(key) for key in value.keys()))
        return type(value).__name__

    def refresh(self, account_id: str) -> AccountState:
        print(f"[AUTONOMOUS][STATE] refresh START account_id={account_id}", flush=True)

        print("[AUTONOMOUS][STATE] portfolio: START", flush=True)
        portfolio = self._portfolio.get_portfolio(account_id)
        print(
            f"[AUTONOMOUS][STATE] portfolio: DONE "
            f"positions={self._collection_count(portfolio, 'positions')} "
            f"keys={self._collection_keys(portfolio)}",
            flush=True,
        )

        print("[AUTONOMOUS][STATE] positions: START", flush=True)
        positions = self._portfolio.get_positions(account_id)
        print(
            f"[AUTONOMOUS][STATE] positions: DONE "
            f"securities={self._collection_count(positions, 'securities')} "
            f"money={self._collection_count(positions, 'money')} "
            f"positions={self._collection_count(positions, 'positions')} "
            f"keys={self._collection_keys(positions)}",
            flush=True,
        )

        # BalanceService exposes get_positions/get_portfolio and build_summary;
        # it does not expose get_balances. Reuse the already fetched API
        # responses so the autonomous state is built from the same snapshot.
        print("[AUTONOMOUS][STATE] balance summary: START", flush=True)
        balance = self._balance.build_summary(positions, portfolio)
        print(
            f"[AUTONOMOUS][STATE] balance summary: DONE "
            f"cash={balance.cash} securities={balance.securities} "
            f"portfolio={balance.portfolio_value} available={balance.available} blocked={balance.blocked}",
            flush=True,
        )

        print("[AUTONOMOUS][STATE] orders: START", flush=True)
        orders = self._orders.get_orders(account_id)
        print(
            f"[AUTONOMOUS][STATE] orders: DONE "
            f"orders={self._collection_count(orders, 'orders')} "
            f"keys={self._collection_keys(orders)}",
            flush=True,
        )
        print("[AUTONOMOUS][STATE] refresh DONE", flush=True)

        return AccountState(portfolio=portfolio, positions=positions, balance=balance, orders=orders)
