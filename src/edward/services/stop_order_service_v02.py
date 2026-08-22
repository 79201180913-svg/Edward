from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4
from typing import Any, Protocol

from edward.services.order_service import OrderSide


@dataclass(frozen=True, slots=True)
class StopOrderRequest:
    account_id: str
    instrument_uid: str
    side: OrderSide
    quantity: int
    stop_price: Decimal
    price: Decimal | None = None
    stop_order_type: str = "STOP_LOSS"
    expiration_type: str = "GOOD_TILL_CANCEL"
    request_id: str = ""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Stop order quantity must be positive")
        if self.stop_price <= 0:
            raise ValueError("Stop price must be positive")
        if not self.request_id:
            object.__setattr__(self, "request_id", str(uuid4()))


class StopOrdersGateway(Protocol):
    def post_stop_order(self, request: dict[str, Any]) -> Any: ...
    def get_stop_orders(self, account_id: str) -> Any: ...
    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> Any: ...


class StopOrderService:
    """Dedicated StopOrdersService application boundary."""

    def __init__(self, gateway: StopOrdersGateway) -> None:
        self._gateway = gateway

    def create(self, request: StopOrderRequest) -> Any:
        payload = {
            "account_id": request.account_id,
            "instrument_uid": request.instrument_uid,
            "direction": request.side.value,
            "quantity": request.quantity,
            "stop_price": {"units": str(int(request.stop_price)), "nano": int((request.stop_price - int(request.stop_price)) * Decimal("1000000000"))},
            "price": None if request.price is None else {"units": str(int(request.price)), "nano": int((request.price - int(request.price)) * Decimal("1000000000"))},
            "stop_order_type": request.stop_order_type,
            "expiration_type": request.expiration_type,
            "request_id": request.request_id,
        }
        return self._gateway.post_stop_order(payload)

    def get_active(self, account_id: str) -> Any:
        return self._gateway.get_stop_orders(account_id)

    def cancel(self, account_id: str, stop_order_id: str) -> Any:
        return self._gateway.cancel_stop_order(account_id, stop_order_id)
