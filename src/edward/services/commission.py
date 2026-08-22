from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CommissionEstimate:
    total_order_amount: Decimal
    commission: Decimal
    currency: str


def normalize_commission(payload: dict) -> CommissionEstimate:
    def dec(value) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, dict):
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        return Decimal(str(value))

    total = dec(payload.get("total_order_amount") or payload.get("initial_order_amount"))
    commission = dec(payload.get("executed_commission")) + dec(payload.get("deal_commission")) + dec(payload.get("service_commission"))
    return CommissionEstimate(total, commission, payload.get("currency", "RUB"))
