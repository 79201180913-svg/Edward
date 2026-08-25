from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


MAX_DAILY_CANDLES = 2400


def _get_candles(
    self: Any,
    instrument_uid: str,
    *,
    interval: str = "CANDLE_INTERVAL_DAY",
    days: int = MAX_DAILY_CANDLES,
) -> dict:
    """Load historical candles through the adapter.

    The protobuf contract exposes candle_source_type, but the REST Sandbox
    currently rejects candleSourceType when limit is supplied (30220).
    Therefore the client deliberately does not send candle_source_type here.
    The adapter keeps the same rule as a second safety boundary.
    """
    days = max(2, min(int(days), MAX_DAILY_CANDLES))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return self._request(
        "POST",
        "/market/candles",
        {
            "instrument_id": str(instrument_uid),
            "from": start.isoformat().replace("+00:00", "Z"),
            "to": end.isoformat().replace("+00:00", "Z"),
            "interval": interval,
            "limit": min(days, MAX_DAILY_CANDLES),
        },
    )


def install(client_class: type[Any]) -> None:
    if getattr(client_class, "_candles_patch_installed", False):
        return
    client_class.get_candles = _get_candles
    client_class._candles_patch_installed = True
