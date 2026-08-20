from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime


class OrderStatus(StrEnum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class OrderSnapshot:
    order_id: str
    account_id: str
    instrument_uid: str
    status: OrderStatus
    requested_quantity: int
    filled_quantity: int
    remaining_quantity: int
    average_fill_price: object | None = None
    commission: object | None = None
    updated_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.ERROR,
        }
