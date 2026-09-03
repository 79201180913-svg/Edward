from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.market_regime_engine_v08 import MarketRegimeEngineV08


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
    """Build point-in-time market-context evidence for a validated path."""

    @staticmethod
    def _excess(value: float | None, baseline: float | None) -> float | None:
        if value is None or baseline is None:
            return None
        return round(float(value) - float(baseline), 10)

    @classmethod
    def _market_returns_for_window(
        cls,
        benchmark_candles: Sequence[Candle],
        *,
        start_timestamp,
        end_timestamp,
        horizon: int,
    ) -> tuple[float, ...]:
        ordered = tuple(sorted(benchmark_candles, key=lambda item: item.timestamp))
        values: list[float] = []
        for index in range(max(0, len(ordered) - horizon)):
            start = ordered[index]
            finish = ordered[index + horizon]
            if not (start_timestamp <= start.timestamp < end_timestamp):
                continue
            if finish.timestamp > end_timestamp:
                continue
            first = float(start.close)
            last = float(finish.close)
            if first > 0.0 and last > 0.0:
                values.append((last / first - 1.0) * 100.0)
        return tuple(values)

    @classmethod
    def _same_regime_baseline(
        cls,
        instrument_candles: Sequence[Candle],
        benchmark_candles: Sequence[Candle],
        *,
        regime: str,
        horizon: int,
        before_timestamp,
    ) -> float | None:
        """Benchmark return during the instrument's historical matching regime.

        Regime labels are classified point-in-time from instrument candles only.
        Benchmark returns are then measured over the same timestamps, preventing
        future benchmark information from influencing the regime label.
        """
        instrument = tuple(sorted(instrument_candles, key=lambda item: item.timestamp))
        benchmark = tuple(sorted(benchmark_candles, key=lambda item: item.timestamp))
        if before_timestamp is None:
            return None

        matching_timestamps: set[object] = set()
        for index in range(len(instrument)):
            anchor = instrument[index]
            if anchor.timestamp >= before_timestamp:
                break
            classified = MarketRegimeEngineV08.classify(instrument[: index + 1])
            if classified.regime == regime:
                matching_timestamps.add(anchor.timestamp)

        if not matching_timestamps:
            return None

        values: list[float] = []
        for index in range(max(0, len(benchmark) - horizon)):
            anchor = benchmark[index]
            finish = benchmark[index + horizon]
            if anchor.timestamp not in matching_timestamps:
                continue
            if finish.timestamp >= before_timestamp:
                continue
            first = float(anchor.close)
            last = float(finish.close)
            if first > 0.0 and last > 0.0:
                values.append((last / first - 1.0) * 100.0)
        return mean(values) if values else None

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

    @classmethod
    def build_from_oos(
        cls,
        *,
        candidate,
        instrument_candles: Sequence[Candle],
        benchmark_candles: Sequence[Candle] | None,
        oos_windows: Sequence[object],
        benchmark_id: str | None = None,
    ) -> TradingPathMarketContextV015:
        ordered = tuple(sorted(instrument_candles, key=lambda item: item.timestamp))
        instrument_returns = tuple(float(item.mean_return_pct) for item in oos_windows)
        instrument_baselines = tuple(float(item.baseline_return_pct) for item in oos_windows)
        instrument_return = mean(instrument_returns) if instrument_returns else None
        instrument_baseline = mean(instrument_baselines) if instrument_baselines else None

        if not benchmark_candles or not oos_windows:
            return cls.build(
                instrument_return_pct=instrument_return,
                instrument_baseline_return_pct=instrument_baseline,
                regime_baseline_return_pct=None,
                market_return_pct=None,
                benchmark_id=benchmark_id,
            )

        horizon = int(candidate.rule.horizon)
        market_window_returns: list[float] = []
        for window in oos_windows:
            if window.start >= len(ordered) or window.end <= window.start:
                continue
            start_timestamp = ordered[window.start].timestamp
            end_timestamp = ordered[min(window.end - 1, len(ordered) - 1)].timestamp
            values = cls._market_returns_for_window(
                benchmark_candles,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                horizon=horizon,
            )
            if values:
                market_window_returns.append(mean(values))

        market_return = mean(market_window_returns) if market_window_returns else None
        first_oos_start = ordered[oos_windows[0].start].timestamp if oos_windows and oos_windows[0].start < len(ordered) else None
        regime_baseline = (
            cls._same_regime_baseline(
                ordered,
                benchmark_candles,
                regime=str(candidate.rule.regime),
                horizon=horizon,
                before_timestamp=first_oos_start,
            )
            if first_oos_start is not None
            else None
        )
        return cls.build(
            instrument_return_pct=instrument_return,
            instrument_baseline_return_pct=instrument_baseline,
            regime_baseline_return_pct=regime_baseline,
            market_return_pct=market_return,
            benchmark_id=benchmark_id,
        )


__all__ = ["MARKET_CONTEXT_VERSION_V015", "TradingPathMarketContextV015", "TradingPathMarketContextServiceV015"]
