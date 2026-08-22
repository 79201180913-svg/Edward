from __future__ import annotations

from typing import Any

from edward.services.order_service import OrderRequest, OrderType


class OrdersApi:
    """Adapter between Edward ordinary-order models and T-Invest OrdersService."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _validate_order_type(request: OrderRequest) -> None:
        if request.order_type not in (OrderType.LIMIT, OrderType.MARKET, OrderType.BESTPRICE):
            raise ValueError(
                "Stop orders must be sent through StopOrdersService; "
                f"unsupported OrdersService type: {request.order_type!r}"
            )

    def post_order(self, request: OrderRequest) -> Any:
        self._validate_order_type(request)
        kwargs = {
            "quantity": request.quantity,
            "direction": request.side.value,
            "account_id": request.account_id,
            "order_type": request.order_type.value,
            "instrument_id": request.instrument_uid,
            "order_id": request.request_id,
        }
        if request.order_type is OrderType.LIMIT:
            kwargs["price"] = request.price
        return self._client.orders.post_order(**kwargs)

    def get_order_state(self, account_id: str, order_id: str) -> Any:
        return self._client.orders.get_order_state(account_id, order_id)

    def get_orders(self, account_id: str) -> Any:
        return self._client.orders.get_orders(account_id)

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        return self._client.orders.cancel_order(account_id, order_id)

    def replace_order(self, request: OrderRequest, order_id: str) -> Any:
        self._validate_order_type(request)
        kwargs = {
            "order_id": order_id,
            "quantity": request.quantity,
            "account_id": request.account_id,
        }
        if request.order_type is OrderType.LIMIT:
            kwargs["price"] = request.price
        return self._client.orders.replace_order(**kwargs)
