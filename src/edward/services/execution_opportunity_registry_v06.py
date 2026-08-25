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


GLOBAL_EXECUTION_OPPORTUNITY_REGISTRY = ExecutionOpportunityRegistry()


def install_live_scan_registry(service_class: type[Any]) -> None:
    if getattr(service_class, "_execution_registry_v06_installed", False):
        return
    original_scan = service_class.scan

    def wrapped_scan(self: Any, *args: Any, **kwargs: Any):
        callback = kwargs.get("result_callback")

        def register_and_forward(item: Any, current: int, total: int) -> None:
            GLOBAL_EXECUTION_OPPORTUNITY_REGISTRY.add(item)
            if callback is not None:
                callback(item, current, total)

        kwargs["result_callback"] = register_and_forward
        results = original_scan(self, *args, **kwargs)
        GLOBAL_EXECUTION_OPPORTUNITY_REGISTRY.replace(list(results))
        return results

    service_class.scan = wrapped_scan
    service_class._execution_registry_v06_installed = True


__all__ = ["ExecutionOpportunityRegistry", "GLOBAL_EXECUTION_OPPORTUNITY_REGISTRY", "install_live_scan_registry"]
