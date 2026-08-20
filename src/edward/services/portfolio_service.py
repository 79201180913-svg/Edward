from __future__ import annotations

from typing import Any

from edward.api.portfolio import PortfolioApi


class PortfolioService:
    """Application service for portfolio and position data."""

    def __init__(self, api: PortfolioApi) -> None:
        self._api = api

    def get_portfolio(self, account_id: str, currency: Any | None = None) -> Any:
        return self._api.get_portfolio(account_id, currency)

    def get_positions(self, account_id: str) -> Any:
        return self._api.get_positions(account_id)
