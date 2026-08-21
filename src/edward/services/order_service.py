from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4
from typing import Any, Protocol


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    account_id: str
    instrument_uid: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Decimal | None = None
    stop_price: Decimal | None = None
    request_id: str = ""
    instrument_kind: str = "SHARE"

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.price is None:
            raise ValueError("Limit price is required for this order type")
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError("Stop price is required for this order type")
        if not self.request_id:
            object.__setattr__(self, "request_id", str(uuid4()))


class OrdersGateway(Protocol):
    def post_order(self, request: OrderRequest) -> Any: ...
    def get_order_state(self, account_id: str, order_id: str) -> Any: ...
    def get_orders(self, account_id: str) -> Any: ...
    def cancel_order(self, account_id: str, order_id: str) -> Any: ...
    def replace_order(self, request: OrderRequest, order_id: str) -> Any: ...
    def get_last_prices(self, instrument_ids: list[str]) -> Any: ...


class OrderService:
    """Application service responsible for all order lifecycle operations."""

    def __init__(self, gateway: OrdersGateway) -> None:
        self._gateway = gateway

    def create_order(self, request: OrderRequest) -> Any:
        # T-Invest PostOrder explicitly ignores price for MARKET orders.
        # The current market price is used by pre-flight validation/confirmation,
        # but must not be injected into the actual MARKET request.
        return self._gateway.post_order(request)

    def get_order_state(self, account_id: str, order_id: str) -> Any:
        return self._gateway.get_order_state(account_id, order_id)

    def get_active_orders(self, account_id: str) -> Any:
        return self._gateway.get_orders(account_id)

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        return self._gateway.cancel_order(account_id, order_id)

    def replace_order(self, account_id: str, order_id: str, request: OrderRequest) -> Any:
        if request.account_id != account_id:
            raise ValueError("Order account does not match active account")
        return self._gateway.replace_order(request, order_id)
