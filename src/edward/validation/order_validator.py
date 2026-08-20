from __future__ import annotations

from decimal import Decimal

from edward.services.order_service import OrderRequest, OrderSide, OrderType


def validate_price_step(price: Decimal, increment: Decimal) -> None:
    if increment <= 0:
        raise ValueError("Price increment must be positive")
    if price <= 0:
        raise ValueError("Price must be positive")
    if price % increment != 0:
        raise ValueError(f"Price {price} does not match minimum price increment {increment}")


def validate_order_request(request: OrderRequest) -> None:
    if not request.account_id:
        raise ValueError("account_id is required")
    if not request.instrument_uid:
        raise ValueError("instrument_uid is required")
    if request.side not in (OrderSide.BUY, OrderSide.SELL):
        raise ValueError("Unsupported order side")
    if request.order_type not in tuple(OrderType):
        raise ValueError("Unsupported order type")
