from __future__ import annotations

from typing import Any


def install(client_class: type[Any]) -> None:
    """Enrich order responses with human-facing ticker values.

    The order API returns instrument_uid reliably, while ticker may be absent.
    Resolve missing tickers through the existing /instruments/get adapter call.
    """
    original = getattr(client_class, "get_orders", None)
    if original is None or getattr(original, "_ticker_fix_wrapped", False):
        return

    def get_orders(self: Any, account_id: str) -> dict:
        result = original(self, account_id)
        if not isinstance(result, dict):
            return result

        orders = result.get("orders")
        if not isinstance(orders, list):
            orders = result.get("items")
        if not isinstance(orders, list):
            return result

        cache: dict[str, str] = {}
        for order in orders:
            if not isinstance(order, dict):
                continue
            ticker = str(order.get("ticker") or "").strip()
            if ticker:
                continue
            instrument_uid = str(order.get("instrument_uid") or "").strip()
            if not instrument_uid:
                continue
            if instrument_uid not in cache:
                try:
                    instrument = self.get_instrument(instrument_uid)
                    if isinstance(instrument, dict):
                        cache[instrument_uid] = str(instrument.get("ticker") or "").strip()
                    else:
                        cache[instrument_uid] = ""
                except Exception:
                    cache[instrument_uid] = ""
            if cache[instrument_uid]:
                order["ticker"] = cache[instrument_uid]

        return result

    get_orders._ticker_fix_wrapped = True
    client_class.get_orders = get_orders
