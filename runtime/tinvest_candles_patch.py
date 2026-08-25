from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _normalize_timestamp(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        seconds = int(value.get("seconds", 0) or 0)
        nanos = int(value.get("nanos", 0) or 0)
        return datetime.fromtimestamp(seconds + nanos / 1_000_000_000, tz=timezone.utc).isoformat()
    return str(value)


def _candles(self, payload: dict[str, Any]) -> dict[str, Any]:
    instrument_id = str(payload.get("instrument_id") or payload.get("instrument_uid") or "")
    if not instrument_id:
        raise ValueError("instrument_id is required")
    start = str(payload.get("from") or "")
    end = str(payload.get("to") or "")
    interval = str(payload.get("interval") or "CANDLE_INTERVAL_DAY")
    limit = max(1, min(int(payload.get("limit", 2400)), 2400))
    request = {
        "from": start,
        "to": end,
        "interval": interval,
        "instrumentId": instrument_id,
        "candleSourceType": str(payload.get("candle_source_type") or "CANDLE_SOURCE_EXCHANGE"),
        "limit": limit,
    }
    return self._rest_request("MarketDataService/GetCandles", request)


def install(adapter_module: Any) -> None:
    state = adapter_module.AdapterState
    if getattr(state, "_candles_patch_installed", False):
        return
    state.candles = _candles
    original = adapter_module.Handler.do_POST

    def do_post(self: Any) -> None:
        if self.path == "/market/candles":
            try:
                payload = self._read_json()
                self._send(200, adapter_module.STATE.candles(payload))
            except Exception as exc:
                adapter_module.logger.exception("[CANDLES ERROR] %s", exc)
                self._send(500, {"error": str(exc), "type": type(exc).__name__})
            return
        original(self)

    adapter_module.Handler.do_POST = do_post
    state._candles_patch_installed = True
