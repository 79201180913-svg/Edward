from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4
from typing import Any, Protocol


class StopOrderKind(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class StopOrderSide(StrEnum):
    BUY = "STOP_ORDER_DIRECTION_BUY"
    SELL = "STOP_ORDER_DIRECTION_SELL"


@dataclass(frozen=True, slots=True)
class StopOrderRequest:
    account_id: str
    instrument_uid: str
    side: StopOrderSide
    kind: StopOrderKind
    quantity: int
    stop_price: Decimal
    request_id: str = ""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Количество лотов должно быть больше 0")
        if self.stop_price <= 0:
            raise ValueError("Стоп-цена должна быть больше 0")
        if not self.request_id:
            object.__setattr__(self, "request_id", str(uuid4()))


class StopOrdersGateway(Protocol):
    def post_stop_order(self, request: dict[str, Any]) -> Any: ...
    def get_stop_orders(self, account_id: str) -> Any: ...
    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> Any: ...


class StopOrderService:
    def __init__(self, gateway: StopOrdersGateway) -> None:
        self._gateway = gateway

    def create_protection(self, request: StopOrderRequest) -> Any:
        return self._gateway.post_stop_order(
            {
                "account_id": request.account_id,
                "instrument_id": request.instrument_uid,
                "direction": request.side.value,
                "quantity": request.quantity,
                "stop_price": request.stop_price,
                "stop_order_type": (
                    "STOP_ORDER_TYPE_STOP_LOSS"
                    if request.kind is StopOrderKind.STOP_LOSS
                    else "STOP_ORDER_TYPE_TAKE_PROFIT"
                ),
                "expiration_type": "STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL",
                "exchange_order_type": "EXCHANGE_ORDER_TYPE_MARKET",
                "take_profit_type": (
                    "TAKE_PROFIT_TYPE_REGULAR"
                    if request.kind is StopOrderKind.TAKE_PROFIT
                    else "TAKE_PROFIT_TYPE_UNSPECIFIED"
                ),
                "price_type": "PRICE_TYPE_CURRENCY",
                "order_id": request.request_id,
            }
        )

    def get_active(self, account_id: str) -> Any:
        return self._gateway.get_stop_orders(account_id)

    def cancel(self, account_id: str, stop_order_id: str) -> Any:
        return self._gateway.cancel_stop_order(account_id, stop_order_id)
