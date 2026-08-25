from __future__ import annotations

from threading import Lock
from typing import Any


class ExecutionOpportunityRegistry:
    """In-process snapshot registry for the current Opportunities scan."""

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}
        self._lock = Lock()

    def replace(self, results: list[Any]) -> None:
        with self._lock:
            self._items = {}
            for item in results:
                key = str(getattr(item, "instrument_uid", "") or getattr(item, "ticker", ""))
                if key:
                    self._items[key] = item

    def add(self, item: Any) -> None:
        key = str(getattr(item, "instrument_uid", "") or getattr(item, "ticker", ""))
        if not key:
            return
        with self._lock:
            self._items[key] = item

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._items:
                return self._items[key]
            return next((item for item in self._items.values() if str(getattr(item, "ticker", "")) == key), None)

    def all(self) -> tuple[Any, ...]:
        with self._lock:
            return tuple(self._items.values())


__all__ = ["ExecutionOpportunityRegistry"]
