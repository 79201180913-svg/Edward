from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Callable

from edward.domain.order_state import OrderSnapshot, OrderStatus


class OrderMonitor:
    """Poll T-Invest order state and normalize API DTOs into OrderSnapshot."""

    def __init__(self, orders_gateway: Any, on_update: Callable[[OrderSnapshot], None] | None = None) -> None:
        self._gateway = orders_gateway
        self._on_update = on_update

    def get_state(self, account_id: str, order_id: str) -> OrderSnapshot:
        response = self._gateway.get_order_state(account_id, order_id)
        return self._to_snapshot(response, account_id, order_id)

    def wait_for_terminal(
        self,
        account_id: str,
        order_id: str,
        interval_seconds: float = 1.0,
        timeout_seconds: float = 300.0,
    ) -> OrderSnapshot:
        started = time.monotonic()
        previous: OrderSnapshot | None = None

        while True:
            snapshot = self.get_state(account_id, order_id)
            if previous != snapshot and self._on_update:
                self._on_update(snapshot)
            previous = snapshot

            if snapshot.is_terminal:
                return snapshot
            if time.monotonic() - started >= timeout_seconds:
                return snapshot
            time.sleep(interval_seconds)

    @staticmethod
    def _read(response: Any, *names: str, default: Any = None) -> Any:
        if isinstance(response, dict):
            for name in names:
                if name in response:
                    return response[name]
            return default
        for name in names:
            value = getattr(response, name, None)
            if value is not None:
                return value
        return default

    @classmethod
    def _number(cls, value: Any, default: int = 0) -> int:
        if isinstance(value, dict):
            if "units" in value or "nano" in value:
                return int(value.get("units", 0))
            for key in ("value", "quantity", "lots_executed", "lots_requested"):
                if key in value:
                    return cls._number(value[key], default)
        try:
            return int(value or default)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _to_snapshot(cls, response: Any, account_id: str, order_id: str) -> OrderSnapshot:
        raw_status = cls._read(response, "execution_report_status", "status", "state", default="UNKNOWN")
        status_value = str(getattr(raw_status, "value", raw_status)).upper()
        mapping = {
            "EXECUTION_REPORT_STATUS_NEW": OrderStatus.NEW,
            "EXECUTION_REPORT_STATUS_EXECUTION_REPORT_STATUS_NEW": OrderStatus.NEW,
            "EXECUTION_REPORT_STATUS_PARTIALLYFILL": OrderStatus.PARTIALLY_FILLED,
            "EXECUTION_REPORT_STATUS_PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "EXECUTION_REPORT_STATUS_FILL": OrderStatus.FILLED,
            "EXECUTION_REPORT_STATUS_CANCELLED": OrderStatus.CANCELLED,
            "EXECUTION_REPORT_STATUS_REJECTED": OrderStatus.REJECTED,
            "NEW": OrderStatus.NEW,
            "ACTIVE": OrderStatus.ACTIVE,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "ERROR": OrderStatus.ERROR,
        }
        status = mapping.get(status_value, OrderStatus.UNKNOWN)

        requested = cls._number(cls._read(response, "lots_requested", "quantity", "requested_quantity"))
        filled = cls._number(cls._read(response, "lots_executed", "filled_quantity", "executed_quantity"))
        remaining = max(requested - filled, 0)

        return OrderSnapshot(
            order_id=order_id,
            account_id=account_id,
            instrument_uid=str(cls._read(response, "instrument_uid", "instrument_id", default="")),
            status=status,
            requested_quantity=requested,
            filled_quantity=filled,
            remaining_quantity=remaining,
            average_fill_price=cls._read(response, "average_position_price", "executed_order_price", "average_fill_price"),
            commission=cls._read(response, "executed_commission", "commission"),
        )
