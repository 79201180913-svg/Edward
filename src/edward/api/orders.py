from __future__ import annotations

from typing import Any

from edward.services.order_service import OrderRequest


class OrdersApi:
    """Adapter between Edward order models and the T-Invest SDK."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def post_order(self, request: OrderRequest) -> Any:
        kwargs = {
            "quantity": request.quantity,
            "direction": request.side.value,
            "account_id": request.account_id,
            "order_type": request.order_type.value,
            "instrument_id": request.instrument_uid,
            "order_id": request.request_id,
        }
        if request.price is not None:
            kwargs["price"] = request.price
        if request.stop_price is not None:
            kwargs["stop_price"] = request.stop_price
        return self._client.orders.post_order(**kwargs)

    def get_order_state(self, account_id: str, order_id: str) -> Any:
        return self._client.orders.get_order_state(account_id, order_id)

    def get_orders(self, account_id: str) -> Any:
        return self._client.orders.get_orders(account_id)

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        return self._client.orders.cancel_order(account_id, order_id)

    def replace_order(self, request: OrderRequest, order_id: str) -> Any:
        kwargs = {
            "order_id": order_id,
            "quantity": request.quantity,
            "account_id": request.account_id,
        }
        if request.price is not None:
            kwargs["price"] = request.price
        return self._client.orders.replace_order(**kwargs)
