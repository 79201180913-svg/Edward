from __future__ import annotations

from decimal import Decimal
from typing import Any


def install(client_class: type[Any]) -> None:
    """Normalize stop-order prices before T-Invest adapter JSON serialization."""
    if getattr(client_class, "_stop_order_json_fix_installed", False):
        return

    original = client_class.post_stop_order

    def post_stop_order(self: Any, request: dict[str, Any]) -> dict:
        payload = dict(request)
        for key in ("stop_price", "price"):
            value = payload.get(key)
            if isinstance(value, Decimal):
                payload[key] = client_class._quotation_payload(value)
        return original(self, payload)

    client_class.post_stop_order = post_stop_order
    client_class._stop_order_json_fix_installed = True
