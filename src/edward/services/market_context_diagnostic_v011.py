from __future__ import annotations

from typing import Any, Sequence

from edward.services.analysis_service import Candle
from edward.services.market_context_ab_backtest_v011 import (
    MarketContextABBacktestResultV011,
    MarketContextABBacktestServiceV011,
)
from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088


class MarketContextDiagnosticV011:
    """Canonical diagnostic facade for point-in-time market-context A/B.

    The facade deliberately sits outside production Quality Gate logic. It
    consumes the same v0.8.8 research adapter used by production analysis and
    compares baseline vs market-aware Top-1/Top-3 selection on future OOS
    observations only.
    """

    def __init__(self, analysis_service_factory=None) -> None:
        self.backtest = MarketContextABBacktestServiceV011(
            analysis_service_factory=analysis_service_factory or __import__(
                "edward.services.analysis_service_v08",
                fromlist=["AnalysisServiceV08"],
            ).AnalysisServiceV08
        )

    @staticmethod
    def cutoffs(candle_count: int, step: int = 120) -> tuple[int, ...]:
        warmup = 300
        oos_tail = 60
        if step <= 0:
            raise ValueError("cutoff step must be positive")
        last_cutoff_exclusive = candle_count - oos_tail
        if last_cutoff_exclusive <= warmup:
            return ()
        return tuple(range(warmup, last_cutoff_exclusive, step))

    def run(
        self,
        *,
        instrument_candles: Sequence[Candle],
        market_candles: Sequence[Candle],
        instrument_uid: str,
        ticker: str,
        profile: str = "medium_term",
        cutoff_step: int = 120,
    ) -> MarketContextABBacktestResultV011:
        instrument = tuple(sorted(instrument_candles, key=lambda item: item.timestamp))
        market = tuple(sorted(market_candles, key=lambda item: item.timestamp))
        if not instrument or not market:
            raise ValueError("instrument_candles and market_candles are required")
        cutoff_indices = self.cutoffs(len(instrument), cutoff_step)
        if not cutoff_indices:
            raise ValueError("Not enough candles for point-in-time A/B diagnostic")
        return self.backtest.run(
            instrument_candles=instrument,
            market_candles=market,
            cutoff_indices=cutoff_indices,
            instrument_uid=instrument_uid,
            ticker=ticker,
            profile=profile,
        )


__all__ = ["MarketContextDiagnosticV011"]
