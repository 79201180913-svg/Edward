from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


MAX_DAILY_CANDLES = 2400


def _get_candles(
    self: Any,
    instrument_uid: str,
    start: Any | None = None,
    end: Any | None = None,
    interval: str = "CANDLE_INTERVAL_DAY",
    limit: int = MAX_DAILY_CANDLES,
    *,
    days: int | None = None,
) -> dict:
    """Load historical candles through the adapter-compatible boundary.

    The client already exposes a five-argument historical-candle contract
    (instrument_id, start, end, interval, limit). This patch must preserve that
    contract because MarketDataLoaderV011 calls it positionally. The legacy
    ``days=`` form remains supported for existing UI callers.

    ``candle_source_type`` is intentionally not sent because the current REST
    Sandbox rejects it when ``limit`` is supplied (30220).
    """
    if days is not None:
        if start is not None or end is not None:
            raise ValueError("days cannot be combined with start/end")
        days = max(2, min(int(days), MAX_DAILY_CANDLES))
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

    if start is None or end is None:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=max(2, min(int(limit), MAX_DAILY_CANDLES)))

    limit = int(limit)
    if limit <= 0:
        raise ValueError("limit must be positive")

    def _iso(value: Any) -> str:
        text = value.isoformat() if hasattr(value, "isoformat") else str(value)
        return text.replace("+00:00", "Z")

    return self._request(
        "POST",
        "/market/candles",
        {
            "instrument_id": str(instrument_uid),
            "from": _iso(start),
            "to": _iso(end),
            "interval": str(interval),
            "limit": min(limit, MAX_DAILY_CANDLES),
        },
    )


def install(client_class: type[Any]) -> None:
    if getattr(client_class, "_candles_patch_installed", False):
        return
    client_class.get_candles = _get_candles
    client_class._candles_patch_installed = True
