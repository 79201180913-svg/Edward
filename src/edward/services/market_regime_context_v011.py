from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from edward.services.analysis_service import Candle
from edward.services.market_regime_engine_v08 import MarketRegimeEngineV08, MarketRegimeResultV08


MARKET_REGIME_CONTEXT_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class MarketRegimeContextV011:
    """Point-in-time market regime context backed by the canonical v0.8 engine."""

    instrument_id: str
    as_of: object
    result: MarketRegimeResultV08
    source_candles: int
    version: str = MARKET_REGIME_CONTEXT_VERSION


class MarketRegimeContextBuilderV011:
    """Build regime context without introducing a second regime classifier."""

    def __init__(self, engine: type[MarketRegimeEngineV08] = MarketRegimeEngineV08) -> None:
        self._engine = engine

    def build(self, instrument_id: str, as_of: object, candles: Iterable[Candle]) -> MarketRegimeContextV011:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        cutoff = self._as_datetime(as_of)
        point_in_time = [item for item in ordered if item.timestamp <= cutoff]
        result = self._engine.classify(point_in_time)
        return MarketRegimeContextV011(
            instrument_id=instrument_id,
            as_of=as_of,
            result=result,
            source_candles=len(point_in_time),
        )

    @staticmethod
    def _as_datetime(value: object):
        if hasattr(value, "tzinfo"):
            return value
        raise TypeError("as_of must be a datetime")


__all__ = ["MARKET_REGIME_CONTEXT_VERSION", "MarketRegimeContextV011", "MarketRegimeContextBuilderV011"]
