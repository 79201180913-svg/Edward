from __future__ import annotations

from typing import Any

from edward.api.portfolio import PortfolioApi


class BalanceService:
    """Application service for account money positions."""

    def __init__(self, api: PortfolioApi) -> None:
        self._api = api

    def get_positions(self, account_id: str) -> Any:
        """Return the raw positions response, including money positions."""
        return self._api.get_positions(account_id)

    @staticmethod
    def get_money_positions(positions_response: Any) -> list[Any]:
        """Extract money positions from GetPositions response."""
        return list(getattr(positions_response, "money", []))

    @staticmethod
    def get_security_positions(positions_response: Any) -> list[Any]:
        """Extract security positions from GetPositions response."""
        return list(getattr(positions_response, "securities", []))
