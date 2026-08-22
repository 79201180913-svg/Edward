from __future__ import annotations

from typing import Any, Protocol


class StopOrdersApi(Protocol):
    """Contract boundary for T-Invest StopOrdersService.

    Implementations must map these operations to the StopOrdersService contract;
    stop orders must never be sent through OrdersService.PostOrder.
    """

    def post_stop_order(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def get_stop_orders(self, account_id: str) -> list[dict[str, Any]]: ...
    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> None: ...
