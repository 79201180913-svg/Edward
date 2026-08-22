from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime


@dataclass(frozen=True)
class Execution:
    order_id: str
    execution_id: str
    instrument_uid: str
    quantity: Decimal
    price: Decimal
    amount: Decimal
    commission: Decimal
    currency: str
    executed_at: datetime | None = None
