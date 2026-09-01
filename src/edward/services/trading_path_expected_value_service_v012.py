from __future__ import annotations

import logging
from typing import Sequence

from edward.domain import TradingPathCandidate
from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import EventObservationBuilderV086
from edward.services.expected_value_engine_v08 import ExpectedValueEngine, ExpectedValueResult
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012

logger = logging.getLogger(__name__)


class TradingPathExpectedValueServiceV012:
    """Calculate EV from realized outcomes of one fixed path on OOS windows."""

    @classmethod
    def outcomes(cls, candidate: TradingPathCandidate, candles: Sequence[Candle], *, windows: int = TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS, test_size: int = TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE, observations=None) -> tuple[float, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        required = windows * test_size
        if windows < 1 or test_size < 1 or len(ordered) < required:
            return ()
        canonical_observations = observations if observations is not None else EventObservationBuilderV086.build(ordered)
        base = len(ordered) - required
        values: list[float] = []
        for offset in range(windows):
            start = base + offset * test_size
            end = base + (offset + 1) * test_size
            for item in canonical_observations:
                if not (start <= item.index < end):
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
    def calculate(cls, candidate: TradingPathCandidate, candles: Sequence[Candle], *, windows: int = TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS, test_size: int = TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE, observations=None) -> ExpectedValueResult:
        values = cls.outcomes(candidate, candles, windows=windows, test_size=test_size, observations=observations)
        result = ExpectedValueEngine.from_returns(values)
        logger.warning("[V012 PATH EV] ticker=%s hypothesis=%s observations=%d ev=%s ci_low=%s ci_high=%s reliability=%s level=%s", candidate.rule.ticker, candidate.rule.hypothesis, result.observations, result.expected_value_pct, result.ev_ci_low_pct, result.ev_ci_high_pct, result.edge_reliability_pct, result.edge_reliability_level)
        return result


__all__ = ["TradingPathExpectedValueServiceV012"]
