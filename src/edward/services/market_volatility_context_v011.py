from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import pstdev
from typing import Sequence

from edward.services.analysis_service import Candle


MARKET_VOLATILITY_CONTEXT_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class VolatilityContextResultV011:
    as_of: datetime
    horizon_bars: int
    instrument_volatility_pct: float | None
    market_volatility_pct: float | None
    relative_volatility: float | None
    classification: str
    version: str = MARKET_VOLATILITY_CONTEXT_VERSION


class MarketVolatilityContextAnalyzerV011:
    """Compare realized close-to-close volatility point-in-time.

    Volatility is annualization-free and expressed as the population standard
    deviation of bar log returns in percent. Keeping the metric local to the
    observation window makes it suitable for contextual conditioning without
    introducing a calendar-frequency assumption.
    """

    @staticmethod
    def _volatility_pct(candles: Sequence[Candle], horizon_bars: int, as_of: datetime) -> float | None:
        ordered = sorted((c for c in candles if c.timestamp <= as_of), key=lambda c: c.timestamp)
        if len(ordered) <= horizon_bars:
            return None
        closes = [float(c.close) for c in ordered[-(horizon_bars + 1):]]
        if any(price <= 0 for price in closes):
            return None
        returns = [__import__("math").log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        if len(returns) < 2:
            return None
        return pstdev(returns) * 100.0 * sqrt(1.0)

    def analyze(
        self,
        *,
        instrument_candles: Sequence[Candle],
        market_candles: Sequence[Candle],
        as_of: datetime,
        horizon_bars: int = 20,
    ) -> VolatilityContextResultV011:
        if horizon_bars < 2:
            raise ValueError("horizon_bars must be >= 2")
        instrument = self._volatility_pct(instrument_candles, horizon_bars, as_of)
        market = self._volatility_pct(market_candles, horizon_bars, as_of)
        if instrument is None or market is None or market == 0:
            return VolatilityContextResultV011(as_of, horizon_bars, instrument, market, None, "UNAVAILABLE")
        relative = instrument / market
        if relative > 1.25:
            classification = "HIGHER_THAN_MARKET"
        elif relative < 0.80:
            classification = "LOWER_THAN_MARKET"
        else:
            classification = "INLINE_WITH_MARKET"
        return VolatilityContextResultV011(as_of, horizon_bars, instrument, market, relative, classification)


__all__ = ["MARKET_VOLATILITY_CONTEXT_VERSION", "VolatilityContextResultV011", "MarketVolatilityContextAnalyzerV011"]
