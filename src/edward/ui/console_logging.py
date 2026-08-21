from __future__ import annotations

from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient

_SENTINEL = "__edward_console_logging_installed__"


def install_console_logging(EdwardApp: Any) -> None:
    if getattr(EdwardApp, _SENTINEL, False):
        return

    original_request = TInvestAdapterClient._request

    def logged_request(self: TInvestAdapterClient, method: str, path: str, payload: dict | None = None) -> dict:
        print(f"[API] {method} {path} payload={payload or {}}", flush=True)
        try:
            result = original_request(self, method, path, payload)
            print(f"[API SUCCESS] {method} {path}", flush=True)
            return result
        except Exception as exc:
            print(f"[API FAILED] {method} {path}: {type(exc).__name__}: {exc}", flush=True)
            raise

    TInvestAdapterClient._request = logged_request
    setattr(EdwardApp, _SENTINEL, True)
