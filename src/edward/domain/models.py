from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Optional


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


class OrderType(StrEnum):
    LIMIT = "limit"
    MARKET = "market"
    BEST_PRICE = "best_price"


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    name: str
    status: str
    account_type: str


@dataclass(frozen=True, slots=True)
class Instrument:
    instrument_uid: str
    ticker: str
    name: str
    currency: str
    instrument_type: str
    figi: Optional[str] = None
    isin: Optional[str] = None
    class_code: Optional[str] = None
    min_price_increment: Optional[Decimal] = None


@dataclass(frozen=True, slots=True)
class MoneyBalance:
    currency: str
    available: Decimal
    blocked: Decimal


@dataclass(frozen=True, slots=True)
class Position:
    instrument_uid: str
    ticker: str
    quantity: Decimal
    blocked: Decimal
    average_price: Decimal
    current_price: Decimal
    value: Decimal
    yield_value: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    account_id: str
    instrument_uid: str
    side: OrderSide
    quantity: Decimal
    filled_quantity: Decimal
    order_type: OrderType
    status: OrderStatus
    price: Optional[Decimal] = None

    @property
    def remaining_quantity(self) -> Decimal:
        return max(self.quantity - self.filled_quantity, Decimal("0"))
