from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ProtectionReconciliationResult:
    status: str
    protected: bool
    reasons: tuple[str, ...] = ()


class ProtectionReconciliationService:
    """Reconcile open long positions with active protective stop orders."""

    def __init__(self, stop_orders: Any) -> None:
        self._stop_orders = stop_orders

    def reconcile(self, *, account_id: str, positions: Any) -> ProtectionReconciliationResult:
        active = self._items(self._stop_orders.get_active(account_id))
        reasons: list[str] = []
        protected = True
        position_uids: set[str] = set()

        for position in self._items(positions):
            uid = str(position.get("instrument_uid", position.get("instrument_id", "")))
            quantity = self._quantity(position)
            if not uid or quantity <= 0:
                continue
            position_uids.add(uid)
            stops = [item for item in active if self._uid(item) == uid and self._active(item)]
            if not stops:
                protected = False
                reasons.append(f"PROTECTION_REQUIRED:{uid}")
                continue
            stop_qty = sum(self._quantity(item) for item in stops)
            if stop_qty != quantity:
                protected = False
                reasons.append(f"PROTECTION_MISMATCH:{uid}:position={quantity}:stop={stop_qty}")

        for item in active:
            uid = self._uid(item)
            if uid and self._active(item) and uid not in position_uids:
                protected = False
                reasons.append(f"ORPHAN_PROTECTION:{uid}")

        if protected:
            return ProtectionReconciliationResult("PROTECTED", True)
        return ProtectionReconciliationResult("RECONCILIATION_ERROR", False, tuple(reasons))

    @staticmethod
    def _items(value: Any) -> tuple[dict[str, Any], ...]:
        if value is None:
            return ()
        if isinstance(value, dict):
            value = value.get("positions", value.get("stop_orders", value.get("orders", ())))
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(item for item in value if isinstance(item, dict))

    @staticmethod
    def _uid(item: dict[str, Any]) -> str:
        return str(item.get("instrument_uid", item.get("instrument_id", "")))

    @staticmethod
    def _quantity(item: dict[str, Any]) -> int:
        value = item.get("quantity", item.get("lots", 0))
        try:
            return int(Decimal(str(value)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _active(item: dict[str, Any]) -> bool:
        return str(item.get("status", "ACTIVE")).upper() not in {"CANCELLED", "EXECUTED", "EXPIRED"}


__all__ = ["ProtectionReconciliationResult", "ProtectionReconciliationService"]
