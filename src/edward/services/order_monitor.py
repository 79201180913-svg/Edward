from __future__ import annotations

import time
from typing import Any, Callable

from edward.domain.order_state import OrderSnapshot, OrderStatus


class OrderMonitor:
    """Polls T-Invest order state and emits state changes."""

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
    def _to_snapshot(response: Any, account_id: str, order_id: str) -> OrderSnapshot:
        status_value = str(getattr(response, "execution_report_status", getattr(response, "status", "UNKNOWN"))).upper()
        mapping = {
            "EXECUTION_REPORT_STATUS_NEW": OrderStatus.NEW,
            "EXECUTION_REPORT_STATUS_PARTIALLYFILL": OrderStatus.PARTIALLY_FILLED,
            "EXECUTION_REPORT_STATUS_FILL": OrderStatus.FILLED,
            "EXECUTION_REPORT_STATUS_CANCELLED": OrderStatus.CANCELLED,
            "EXECUTION_REPORT_STATUS_REJECTED": OrderStatus.REJECTED,
            "NEW": OrderStatus.NEW,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
        }
        status = mapping.get(status_value, OrderStatus.UNKNOWN)
        requested = int(getattr(response, "lots_requested", getattr(response, "quantity", 0)) or 0)
        filled = int(getattr(response, "lots_executed", getattr(response, "filled_quantity", 0)) or 0)
        remaining = max(requested - filled, 0)
        return OrderSnapshot(
            order_id=order_id,
            account_id=account_id,
            instrument_uid=str(getattr(response, "instrument_uid", "")),
            status=status,
            requested_quantity=requested,
            filled_quantity=filled,
            remaining_quantity=remaining,
            average_fill_price=getattr(response, "average_position_price", None),
            commission=getattr(response, "executed_commission", None),
        )
