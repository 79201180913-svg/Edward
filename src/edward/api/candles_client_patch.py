from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _get_candles(self: Any, instrument_uid: str, *, interval: str = "CANDLE_INTERVAL_DAY", days: int = 2400) -> dict:
    days = max(2, min(int(days), 2400))
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
            "candle_source_type": "CANDLE_SOURCE_EXCHANGE",
            "limit": 2400,
        },
    )


def install(client_class: type[Any]) -> None:
    if getattr(client_class, "_candles_patch_installed", False):
        return
    client_class.get_candles = _get_candles
    client_class._candles_patch_installed = True
