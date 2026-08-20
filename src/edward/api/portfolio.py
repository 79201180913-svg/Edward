from __future__ import annotations

from typing import Any


class PortfolioApi:
    """Adapter for T-Invest OperationsService portfolio operations."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_portfolio(self, account_id: str, currency: Any | None = None) -> Any:
        kwargs: dict[str, Any] = {"account_id": account_id}
        if currency is not None:
            kwargs["currency"] = currency
        return self._client.operations.get_portfolio(**kwargs)

    def get_positions(self, account_id: str) -> Any:
        return self._client.operations.get_positions(account_id=account_id)
