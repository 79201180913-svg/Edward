from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Sequence

from edward.domain import TradingPathCandidate
from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import EventObservationBuilderV086
from edward.services.trading_path_adaptive_oos_service_v014 import TradingPathAdaptiveOOSServiceV014
from edward.services.trading_path_validation_service_v012 import TradingPathValidationServiceV012

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TradingPathOOSWindowV012:
    index: int
    start: int
    end: int
    observations: int
    mean_return_pct: float
    baseline_return_pct: float
    excess_return_pct: float
    win_rate_pct: float
    positive: bool
    returns_pct: tuple[float, ...] = ()


class TradingPathOOSValidationServiceV012:
    """Temporal OOS validation for a concrete path.

    Fixed and adaptive candidates share the same window, baseline, summary and
    validation contract. Adaptive matching is delegated to the v0.8.14
    point-in-time evaluator; no evaluation-partition thresholds are derived.
    """

    MIN_OOS_OBSERVATIONS = 3
    DEFAULT_WINDOWS = 4
    DEFAULT_TEST_SIZE = 30

    @classmethod
    def _evaluate_window(cls, candidate, observations, candles, start, end, index):
        if TradingPathAdaptiveOOSServiceV014.is_adaptive(candidate):
            values = list(
                TradingPathAdaptiveOOSServiceV014.returns_in_range(
                    candidate, candles, start=start, end=end
                )
            )
        else:
            path_events = [
                item for item in observations
                if start <= item.index < end
                and item.hypothesis == candidate.rule.hypothesis
                and item.regime == candidate.rule.regime
                and item.volatility_bucket == candidate.rule.volatility_bucket
                and item.direction == candidate.rule.direction
            ]
            values = []
            horizon = candidate.rule.horizon
            for item in path_events:
                finish = item.index + horizon
                if finish >= len(candles):
                    continue
                start_close = float(candles[item.index].close)
                finish_close = float(candles[finish].close)
                if start_close <= 0 or finish_close <= 0:
                    continue
                values.append((finish_close / start_close - 1.0) * 100.0)

        baseline = []
        horizon = candidate.rule.horizon
        for index_ in range(start, min(end, len(candles) - horizon)):
            a = float(candles[index_].close)
            b = float(candles[index_ + horizon].close)
            if a > 0 and b > 0:
                baseline.append((b / a - 1.0) * 100.0)
        event_mean = mean(values) if values else 0.0
        baseline_mean = mean(baseline) if baseline else 0.0
        return TradingPathOOSWindowV012(
            index=index, start=start, end=end, observations=len(values),
            mean_return_pct=event_mean, baseline_return_pct=baseline_mean,
            excess_return_pct=event_mean - baseline_mean,
            win_rate_pct=sum(value > 0 for value in values) / len(values) * 100.0 if values else 0.0,
            positive=bool(values) and event_mean - baseline_mean > 0.0,
            returns_pct=tuple(values),
        )

    @classmethod
    def validate(cls, candidate: TradingPathCandidate, candles: Sequence[Candle], *, windows=DEFAULT_WINDOWS, test_size=DEFAULT_TEST_SIZE, observations=None):
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        if windows < 1 or test_size < 1:
            raise ValueError("windows and test_size must be positive")
        required = windows * test_size
        if len(ordered) < required:
            logger.warning("[V012 PATH OOS] insufficient candles=%d required=%d ticker=%s", len(ordered), required, candidate.rule.ticker)
            return ()
        canonical_observations = observations if observations is not None else EventObservationBuilderV086.build(ordered)
        base = len(ordered) - required
        return tuple(
            cls._evaluate_window(candidate, canonical_observations, ordered, base + offset * test_size, base + (offset + 1) * test_size, offset + 1)
            for offset in range(windows)
        )

    @classmethod
    def build_validation(cls, candidate, candles: Sequence[Candle], *, windows=DEFAULT_WINDOWS, test_size=DEFAULT_TEST_SIZE, observations=None):
        result = cls.validate(candidate, candles, windows=windows, test_size=test_size, observations=observations)
        positive_pct = sum(item.positive for item in result) / len(result) * 100.0 if result else None
        robustness = None
        if result:
            mean_excess = mean(item.excess_return_pct for item in result)
            dispersion = pstdev(item.excess_return_pct for item in result) if len(result) > 1 else 0.0
            robustness = max(0.0, min(100.0, 50.0 + mean_excess / max(dispersion, 1.0) * 10.0))
        sufficient = bool(result) and all(item.observations >= cls.MIN_OOS_OBSERVATIONS for item in result)
        statistical_valid = sufficient and mean(item.excess_return_pct for item in result) > 0.0 if result else False
        return TradingPathValidationServiceV012.validate(
            candidate, wf_persistence_pct=positive_pct, robustness_score=robustness,
            positive_oos_windows_pct=positive_pct, statistical_valid=statistical_valid,
            overlap_valid=None, multiple_testing_valid=None,
            promotion_status="validated" if statistical_valid else "rejected",
        )


__all__ = ["TradingPathOOSWindowV012", "TradingPathOOSValidationServiceV012"]
