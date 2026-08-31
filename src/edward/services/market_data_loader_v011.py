from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Sequence

from edward.services.analysis_service import Candle


MARKET_DATA_LOADER_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class MarketDataRequest:
    instrument_id: str
    start: datetime
    end: datetime
    interval: str = "CANDLE_INTERVAL_DAY"
    limit: int = 2400


class MarketDataLoaderV011:
    """Load normalized candles through an injected market-data boundary.

    This service deliberately owns no broker/network client. The caller injects
    a callable returning the adapter response, which keeps research code
    deterministic and easy to test. The loader preserves the requested
    point-in-time interval and never extends `end` implicitly.
    """

    def __init__(self, fetcher: Callable[..., Any]) -> None:
        self._fetcher = fetcher

    def load(self, request: MarketDataRequest) -> list[Candle]:
        if request.start >= request.end:
            raise ValueError("Market data start must be earlier than end")
        if request.limit <= 0:
            raise ValueError("Market data limit must be positive")

        response = self._fetcher(
            request.instrument_id,
            request.start,
            request.end,
            request.interval,
            request.limit,
        )
        raw = self._items(response)
        candles = [self._candle(item) for item in raw]
        candles.sort(key=lambda item: item.timestamp)
        return candles

    @staticmethod
    def _items(response: Any) -> list[Any]:
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in ("candles", "items"):
                value = response.get(key)
                if value is not None:
                    return list(value or [])
        for key in ("candles", "items"):
            value = getattr(response, key, None)
            if value is not None:
                return list(value or [])
        return []

    @classmethod
    def _candle(cls, item: Any) -> Candle:
        timestamp = cls._value(item, "time", "timestamp")
        if timestamp is None:
            raise ValueError("Market candle is missing timestamp")
        timestamp = cls._timestamp(timestamp)
        return Candle(
            timestamp=timestamp,
            open=cls._number(cls._value(item, "open")),
            high=cls._number(cls._value(item, "high")),
            low=cls._number(cls._value(item, "low")),
            close=cls._number(cls._value(item, "close")),
            volume=cls._number(cls._value(item, "volume", "volume_units", default=0.0)),
        )

    @staticmethod
    def _value(item: Any, *names: str, default: Any = None) -> Any:
        for name in names:
            if isinstance(item, dict) and name in item:
                return item[name]
            if hasattr(item, name):
                return getattr(item, name)
        return default

    @staticmethod
    def _number(value: Any) -> float:
        if isinstance(value, dict) and ("units" in value or "nano" in value):
            return float(Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000"))
        if value is None:
            return 0.0
        return float(value)

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


__all__ = ["MARKET_DATA_LOADER_VERSION", "MarketDataRequest", "MarketDataLoaderV011"]
