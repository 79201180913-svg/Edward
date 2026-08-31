from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from edward.services.analysis_service import Candle


RELATIVE_STRENGTH_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class RelativeStrengthResultV011:
    as_of: datetime
    horizon_bars: int
    instrument_return_pct: float | None
    market_return_pct: float | None
    excess_return_pct: float | None
    classification: str
    version: str = RELATIVE_STRENGTH_VERSION


class RelativeStrengthAnalyzerV011:
    """Compare instrument and benchmark returns using point-in-time data only."""

    @staticmethod
    def _return_pct(candles: Sequence[Candle], horizon_bars: int, as_of: datetime) -> float | None:
        ordered = sorted((c for c in candles if c.timestamp <= as_of), key=lambda c: c.timestamp)
        if len(ordered) <= horizon_bars:
            return None
        start = float(ordered[-(horizon_bars + 1)].close)
        end = float(ordered[-1].close)
        if start == 0:
            return None
        return (end / start - 1.0) * 100.0

    def analyze(
        self,
        *,
        instrument_candles: Sequence[Candle],
        market_candles: Sequence[Candle],
        as_of: datetime,
        horizon_bars: int = 20,
    ) -> RelativeStrengthResultV011:
        if horizon_bars < 1:
            raise ValueError("horizon_bars must be >= 1")
        instrument_return = self._return_pct(instrument_candles, horizon_bars, as_of)
        market_return = self._return_pct(market_candles, horizon_bars, as_of)
        if instrument_return is None or market_return is None:
            return RelativeStrengthResultV011(
                as_of=as_of,
                horizon_bars=horizon_bars,
                instrument_return_pct=instrument_return,
                market_return_pct=market_return,
                excess_return_pct=None,
                classification="UNAVAILABLE",
            )
        excess = instrument_return - market_return
        classification = "OUTPERFORMING" if excess > 0 else "UNDERPERFORMING" if excess < 0 else "INLINE"
        return RelativeStrengthResultV011(
            as_of=as_of,
            horizon_bars=horizon_bars,
            instrument_return_pct=instrument_return,
            market_return_pct=market_return,
            excess_return_pct=excess,
            classification=classification,
        )


__all__ = ["RELATIVE_STRENGTH_VERSION", "RelativeStrengthResultV011", "RelativeStrengthAnalyzerV011"]
