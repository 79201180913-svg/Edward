from __future__ import annotations

from dataclasses import dataclass


MARKET_CONTEXT_VERSION_V015 = "0.8.15"


@dataclass(frozen=True, slots=True)
class TradingPathMarketContextV015:
    """Return-relative market context evidence for one trading path.

    The service is deliberately decision-independent. It measures the path
    against the instrument baseline, the same-regime baseline and the market
    benchmark. It does not apply a BUY/WAIT/PASS threshold.
    """

    benchmark_id: str | None
    instrument_return_pct: float | None
    instrument_baseline_return_pct: float | None
    regime_baseline_return_pct: float | None
    market_return_pct: float | None
    instrument_excess_pct: float | None
    regime_excess_pct: float | None
    market_excess_pct: float | None
    relative_strength_pct: float | None
    context_status: str
    version: str = MARKET_CONTEXT_VERSION_V015


class TradingPathMarketContextServiceV015:
    """Build market-context evidence without changing canonical decisions."""

    @staticmethod
    def _excess(value: float | None, baseline: float | None) -> float | None:
        if value is None or baseline is None:
            return None
        return round(float(value) - float(baseline), 10)

    @classmethod
    def build(
        cls,
        *,
        instrument_return_pct: float | None,
        instrument_baseline_return_pct: float | None,
        regime_baseline_return_pct: float | None,
        market_return_pct: float | None,
        benchmark_id: str | None = None,
    ) -> TradingPathMarketContextV015:
        instrument_excess = cls._excess(instrument_return_pct, instrument_baseline_return_pct)
        regime_excess = cls._excess(instrument_return_pct, regime_baseline_return_pct)
        market_excess = cls._excess(instrument_return_pct, market_return_pct)

        available = [regime_excess is not None, market_excess is not None]
        if all(available):
            status = "FULL"
        elif any(available):
            status = "PARTIAL"
        else:
            status = "UNAVAILABLE"

        return TradingPathMarketContextV015(
            benchmark_id=benchmark_id,
            instrument_return_pct=(round(float(instrument_return_pct), 10) if instrument_return_pct is not None else None),
            instrument_baseline_return_pct=(round(float(instrument_baseline_return_pct), 10) if instrument_baseline_return_pct is not None else None),
            regime_baseline_return_pct=(round(float(regime_baseline_return_pct), 10) if regime_baseline_return_pct is not None else None),
            market_return_pct=(round(float(market_return_pct), 10) if market_return_pct is not None else None),
            instrument_excess_pct=instrument_excess,
            regime_excess_pct=regime_excess,
            market_excess_pct=market_excess,
            relative_strength_pct=market_excess,
            context_status=status,
        )


__all__ = ["MARKET_CONTEXT_VERSION_V015", "TradingPathMarketContextV015", "TradingPathMarketContextServiceV015"]
