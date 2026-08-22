from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class OrderNotification:
    order_id: str
    event: str
    message: str


class NotificationService:
    EVENTS = {"CREATED", "ACTIVE", "PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED", "ERROR"}

    def __init__(self, sink: Callable[[OrderNotification], None] | None = None) -> None:
        self._sink = sink

    def notify(self, order_id: str, event: str, message: str) -> None:
        event = event.upper()
        if event not in self.EVENTS:
            raise ValueError(f"Unsupported order event: {event}")
        notification = OrderNotification(order_id, event, message)
        if self._sink:
            self._sink(notification)
