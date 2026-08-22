from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PreflightContext:
    buy_available: bool = True
    sell_available: bool = True
    trading_open: bool = True
    available_cash: Decimal = Decimal("0")
    available_quantity: Decimal = Decimal("0")
    estimated_total: Decimal = Decimal("0")


def validate_order(*, side: str, quantity: Decimal, price: Decimal | None, min_price_increment: Decimal | None, context: PreflightContext) -> None:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    if not context.trading_open:
        raise ValueError("Trading session is closed")
    if side.upper() == "BUY" and not context.buy_available:
        raise ValueError("Instrument is not available for buying")
    if side.upper() == "SELL" and not context.sell_available:
        raise ValueError("Instrument is not available for selling")
    if side.upper() == "SELL" and quantity > context.available_quantity:
        raise ValueError("Insufficient available position")
    if side.upper() == "BUY" and context.estimated_total > context.available_cash:
        raise ValueError("Insufficient available funds")
    if price is not None:
        if price <= 0:
            raise ValueError("Price must be positive")
        if min_price_increment and min_price_increment > 0:
            units = price / min_price_increment
            if units != units.to_integral_value():
                raise ValueError("Price does not match min_price_increment")
