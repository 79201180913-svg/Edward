from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import (
    DIRECTIONS,
    HORIZONS,
    HYPOTHESES,
    MIN_LOOKBACK,
    VOLATILITY_BUCKETS,
    EventObservationBuilderV086,
    EventObservationV086,
)
from edward.services.regime_engine_v08 import RegimeEngine

logger = logging.getLogger(__name__)
CONDITIONAL_DISCOVERY_VERSION = "0.8.6"


@dataclass(frozen=True, slots=True)
class ConditionalDiscoveryCell:
    hypothesis: str
    regime: str
    volatility_bucket: str
    direction: str
    horizon: int
    observations: int
    mean_forward_return_pct: float
    median_forward_return_pct: float
    win_rate_pct: float
    baseline_mean_return_pct: float
    excess_return_pct: float
    sufficient_sample: bool


@dataclass(frozen=True, slots=True)
class ConditionalDiscoveryEvidence:
    hypothesis: str
    events: int
    cells: tuple[ConditionalDiscoveryCell, ...]

    @property
    def sufficient_cells(self) -> int:
        return sum(cell.sufficient_sample for cell in self.cells)

    @property
    def positive_excess_cells(self) -> int:
        return sum(cell.sufficient_sample and cell.excess_return_pct > 0 for cell in self.cells)


@dataclass(frozen=True, slots=True)
class ConditionalDiscoveryResult:
    version: str
    candles: int
    min_observations: int
    evidence: tuple[ConditionalDiscoveryEvidence, ...]
    observations: tuple[EventObservationV086, ...] = ()


class ConditionalDiscoveryServiceV086:
    """Conditional event study over one canonical EventObservation set."""

    HORIZONS = HORIZONS
    MIN_LOOKBACK = MIN_LOOKBACK
    MIN_OBSERVATIONS = 8
    REGIMES = RegimeEngine.REGIMES
    VOLATILITY_BUCKETS = VOLATILITY_BUCKETS
    DIRECTIONS = DIRECTIONS
    HYPOTHESES = HYPOTHESES

    @staticmethod
    def _forward_return(candles: Sequence[Candle], index: int, horizon: int) -> float | None:
        """Return the forward close-to-close return for a canonical event."""
        end = index + horizon
        if index < 0 or end >= len(candles):
            return None
        start = float(candles[index].close)
        finish = float(candles[end].close)
        if start <= 0 or finish <= 0:
            return None
        return finish / start - 1.0

    @classmethod
    def run(cls, candles: Sequence[Candle]) -> ConditionalDiscoveryResult:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        logger.warning(
            "[V086 CONDITIONAL DISCOVERY START] candles=%d hypotheses=%d horizons=%s",
            len(ordered), len(cls.HYPOTHESES), cls.HORIZONS,
        )
        if len(ordered) < cls.MIN_LOOKBACK + 1:
            return ConditionalDiscoveryResult(CONDITIONAL_DISCOVERY_VERSION, len(ordered), cls.MIN_OBSERVATIONS, ())

        observations = EventObservationBuilderV086.build(ordered)
        baselines = {
            horizon: [
                (float(ordered[index + horizon].close) / float(ordered[index].close) - 1.0) * 100.0
                for index in range(len(ordered) - horizon)
                if float(ordered[index].close) > 0 and float(ordered[index + horizon].close) > 0
            ]
            for horizon in cls.HORIZONS
        }
        evidence: list[ConditionalDiscoveryEvidence] = []
        for hypothesis in cls.HYPOTHESES:
            hypothesis_observations = tuple(item for item in observations if item.hypothesis == hypothesis)
            cells: list[ConditionalDiscoveryCell] = []
            for regime in cls.REGIMES:
                for volatility in cls.VOLATILITY_BUCKETS:
                    for direction in cls.DIRECTIONS:
                        matching = tuple(
                            item for item in hypothesis_observations
                            if item.regime == regime and item.volatility_bucket == volatility and item.direction == direction
                        )
                        for horizon in cls.HORIZONS:
                            values = tuple(
                                value for item in matching
                                if (value := item.forward_return(horizon)) is not None
                            )
                            baseline = baselines[horizon]
                            baseline_mean = mean(baseline) if baseline else 0.0
                            event_mean = mean(values) if values else 0.0
                            cells.append(ConditionalDiscoveryCell(
                                hypothesis, regime, volatility, direction, horizon, len(values),
                                event_mean, median(values) if values else 0.0,
                                sum(value > 0 for value in values) / len(values) * 100.0 if values else 0.0,
                                baseline_mean, event_mean - baseline_mean,
                                len(values) >= cls.MIN_OBSERVATIONS,
                            ))
            item = ConditionalDiscoveryEvidence(hypothesis, len(hypothesis_observations), tuple(cells))
            logger.warning(
                "[V086 CONDITIONAL HYPOTHESIS] hypothesis=%s events=%d sufficient_cells=%d positive_excess_cells=%d",
                hypothesis, item.events, item.sufficient_cells, item.positive_excess_cells,
            )
            evidence.append(item)
        return ConditionalDiscoveryResult(
            CONDITIONAL_DISCOVERY_VERSION, len(ordered), cls.MIN_OBSERVATIONS,
            tuple(evidence), observations,
        )


__all__ = [
    "CONDITIONAL_DISCOVERY_VERSION", "ConditionalDiscoveryCell",
    "ConditionalDiscoveryEvidence", "ConditionalDiscoveryResult",
    "ConditionalDiscoveryServiceV086",
]
