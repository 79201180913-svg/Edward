from __future__ import annotations

import logging
from typing import Sequence

from edward.domain import TradingPathCandidate
from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import EventObservationBuilderV086
from edward.services.expected_value_engine_v08 import ExpectedValueEngine, ExpectedValueResult
from edward.services.trading_path_adaptive_oos_service_v014 import TradingPathAdaptiveOOSServiceV014
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012

logger = logging.getLogger(__name__)


class TradingPathExpectedValueServiceV012:
    """Calculate EV from realized outcomes on an explicit evaluation range."""

    @classmethod
    def outcomes(
        cls,
        candidate: TradingPathCandidate,
        candles: Sequence[Candle],
        *,
        windows: int = TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS,
        test_size: int = TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE,
        observations=None,
        evaluation_start: int | None = None,
        evaluation_end: int | None = None,
    ) -> tuple[float, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        if windows < 1 or test_size < 1:
            return ()

        if evaluation_start is not None or evaluation_end is not None:
            start = 0 if evaluation_start is None else evaluation_start
            end = len(ordered) if evaluation_end is None else evaluation_end
            if start < 0 or end < start or end > len(ordered):
                return ()
            required = windows * test_size
            if end - start < required:
                return ()
            base = end - required
        else:
            required = windows * test_size
            if len(ordered) < required:
                return ()
            base = len(ordered) - required

        if TradingPathAdaptiveOOSServiceV014.is_adaptive(candidate):
            values: list[float] = []
            for offset in range(windows):
                window_start = base + offset * test_size
                window_end = base + (offset + 1) * test_size
                values.extend(
                    TradingPathAdaptiveOOSServiceV014.returns_in_range(
                        candidate, ordered, start=window_start, end=window_end
                    )
                )
            return tuple(values)

        canonical_observations = observations if observations is not None else EventObservationBuilderV086.build(ordered)
        values: list[float] = []
        for offset in range(windows):
            window_start = base + offset * test_size
            window_end = base + (offset + 1) * test_size
            for item in canonical_observations:
                if not (window_start <= item.index < window_end):
                    continue
                if item.hypothesis != candidate.rule.hypothesis or item.regime != candidate.rule.regime or item.volatility_bucket != candidate.rule.volatility_bucket or item.direction != candidate.rule.direction:
                    continue
                finish = item.index + candidate.rule.horizon
                if finish >= len(ordered):
                    continue
                start_close = float(ordered[item.index].close)
                finish_close = float(ordered[finish].close)
                if start_close > 0.0 and finish_close > 0.0:
                    values.append((finish_close / start_close - 1.0) * 100.0)
        return tuple(values)

    @classmethod
    def calculate(
        cls,
        candidate: TradingPathCandidate,
        candles: Sequence[Candle],
        *,
        windows: int = TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS,
        test_size: int = TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE,
        observations=None,
        evaluation_start: int | None = None,
        evaluation_end: int | None = None,
    ) -> ExpectedValueResult:
        values = cls.outcomes(
            candidate, candles, windows=windows, test_size=test_size,
            observations=observations, evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
        result = ExpectedValueEngine.from_returns(values)
        logger.warning(
            "[V012 PATH EV] ticker=%s hypothesis=%s observations=%d ev=%s ci_low=%s ci_high=%s reliability=%s level=%s",
            candidate.rule.ticker, candidate.rule.hypothesis, result.observations,
            result.expected_value_pct, result.ev_ci_low_pct, result.ev_ci_high_pct,
            result.edge_reliability_pct, result.edge_reliability_level,
        )
        return result


__all__ = ["TradingPathExpectedValueServiceV012"]
