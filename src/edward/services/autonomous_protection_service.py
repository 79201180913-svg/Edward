from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from edward.services.stop_order_service import StopOrderKind, StopOrderRequest, StopOrderService, StopOrderSide


@dataclass(frozen=True, slots=True)
class ProtectionResult:
    protected: bool
    status: str
    stop_order_id: str | None = None
    reason: str = ""


class AutonomousProtectionService:
    """Create, verify and recover protective stops for autonomous long positions."""

    def __init__(self, stop_orders: StopOrderService) -> None:
        self._stop_orders = stop_orders

    def protect_fill(self, *, account_id: str, instrument_uid: str, quantity: int, result: Any) -> ProtectionResult:
        action = str(getattr(result, "decision", "") or "").upper()
        if action not in {"BUY", "ADD"}:
            return ProtectionResult(True, "NOT_REQUIRED")
        trade_plan = getattr(result, "trade_plan", None)
        stop_price = getattr(result, "stop_price", None)
        if stop_price is None and trade_plan is not None:
            stop_price = getattr(trade_plan, "stop_price", None)
        return self._ensure(account_id=account_id, instrument_uid=instrument_uid, quantity=quantity, stop_price=stop_price)

    def recover_position(self, *, account_id: str, instrument_uid: str, quantity: int, stop_price: Decimal | int | float | str) -> ProtectionResult:
        """Restore missing protection for an already-open position; never creates protection without an explicit stop price."""
        return self._ensure(account_id=account_id, instrument_uid=instrument_uid, quantity=quantity, stop_price=stop_price)

    def _ensure(self, *, account_id: str, instrument_uid: str, quantity: int, stop_price: Any) -> ProtectionResult:
        if quantity <= 0:
            return ProtectionResult(False, "STOPPED", reason="INVALID_FILLED_QUANTITY")
        if stop_price is None:
            return ProtectionResult(False, "STOPPED", reason="PROTECTION_STOP_PRICE_MISSING")
        try:
            stop_price = Decimal(str(stop_price))
        except (TypeError, ValueError):
            return ProtectionResult(False, "STOPPED", reason="PROTECTION_STOP_PRICE_INVALID")
        if stop_price <= 0:
            return ProtectionResult(False, "STOPPED", reason="PROTECTION_STOP_PRICE_INVALID")

        active = self._stop_orders.get_active(account_id)
        for item in self._items(active):
            item_uid = str(item.get("instrument_uid", item.get("instrument_id", "")))
            if item_uid == instrument_uid and str(item.get("status", "ACTIVE")).upper() not in {"CANCELLED", "EXECUTED", "EXPIRED"}:
                return ProtectionResult(True, "PROTECTED", stop_order_id=str(item.get("stop_order_id", item.get("order_id", ""))) or None)

        request = StopOrderRequest(account_id=account_id, instrument_uid=instrument_uid, side=StopOrderSide.SELL, kind=StopOrderKind.STOP_LOSS, quantity=quantity, stop_price=stop_price)
        created = self._stop_orders.create_protection(request)
        stop_order_id = self._id(created)
        active_after = self._stop_orders.get_active(account_id)
        if not self._contains(active_after, instrument_uid, stop_order_id):
            return ProtectionResult(False, "STOPPED", stop_order_id=stop_order_id, reason="PROTECTION_NOT_VERIFIED")
        return ProtectionResult(True, "PROTECTED", stop_order_id=stop_order_id)

    @staticmethod
    def _items(value: Any) -> tuple[dict[str, Any], ...]:
        if value is None: return ()
        if isinstance(value, dict): value = value.get("stop_orders", value.get("orders", ()))
        if not isinstance(value, (list, tuple)): return ()
        return tuple(item for item in value if isinstance(item, dict))

    @classmethod
    def _contains(cls, value: Any, instrument_uid: str, stop_order_id: str | None) -> bool:
        return any(str(item.get("instrument_uid", item.get("instrument_id", ""))) == instrument_uid and (not stop_order_id or str(item.get("stop_order_id", item.get("order_id", ""))) == stop_order_id) for item in cls._items(value))

    @staticmethod
    def _id(value: Any) -> str | None:
        if isinstance(value, dict): return str(value.get("stop_order_id", value.get("order_id", ""))) or None
        return str(getattr(value, "stop_order_id", getattr(value, "order_id", ""))) or None


__all__ = ["AutonomousProtectionService", "ProtectionResult"]
