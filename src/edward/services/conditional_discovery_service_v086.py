from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Sequence

from edward.services.analysis_service import Candle
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


class ConditionalDiscoveryServiceV086:
    """Conditional event-study layer.

    Discovery remains descriptive: it does not select production parameters,
    bypass Robust Walk-Forward, or change Quality Gate admissibility.
    """

    HORIZONS = (1, 3, 5, 10, 20)
    MIN_LOOKBACK = 20
    MIN_OBSERVATIONS = 8
    HYPOTHESES = (
        "BREAKOUT_EXPANSION",
        "PULLBACK_RECLAIM",
        "IMPULSE_CONTINUATION",
        "SHOCK_REVERSAL",
        "GAP_REVERSAL",
        "RANGE_BREAK",
    )
    VOLATILITY_BUCKETS = ("Low", "Normal", "High")
    DIRECTIONS = ("Positive", "Negative")

    @staticmethod
    def _forward_return(candles: Sequence[Candle], index: int, horizon: int) -> float | None:
        end = index + horizon
        if index < 0 or end >= len(candles):
            return None
        start = float(candles[index].close)
        finish = float(candles[end].close)
        return finish / start - 1.0 if start > 0 and finish > 0 else None

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return [
            float(current.close) / float(previous.close) - 1.0
            for previous, current in zip(candles, candles[1:])
            if float(previous.close) > 0 and float(current.close) > 0
        ]

    @classmethod
    def _volatility_bucket(cls, candles: Sequence[Candle], index: int) -> str:
        returns = cls._returns(candles[max(0, index - 20): index + 1])
        if len(returns) < 5:
            return "Normal"
        sigma = pstdev(returns)
        # Relative thresholds keep the classifier simple and deterministic.
        if sigma < 0.0075:
            return "Low"
        if sigma > 0.02:
            return "High"
        return "Normal"

    @staticmethod
    def _direction(candles: Sequence[Candle], index: int) -> str:
        if index < 1:
            return "Positive"
        return "Positive" if float(candles[index].close) >= float(candles[index - 1].close) else "Negative"

    @classmethod
    def _event_indices(cls, candles: Sequence[Candle], hypothesis: str) -> list[int]:
        closes = [float(c.close) for c in candles]
        opens = [float(c.open) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        indices: list[int] = []
        for index in range(cls.MIN_LOOKBACK, len(candles)):
            if closes[index] <= 0:
                continue
            if hypothesis == "BREAKOUT_EXPANSION":
                prior_high = max(highs[index - 20:index])
                tr = max(highs[index] - lows[index], abs(highs[index] - closes[index - 1]), abs(lows[index] - closes[index - 1]))
                prior_tr = [max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1])) for j in range(index - 20, index)]
                if prior_tr and tr >= median(prior_tr) * 1.5 and closes[index] >= prior_high:
                    indices.append(index)
            elif hypothesis == "PULLBACK_RECLAIM":
                fast = mean(closes[index - 10:index])
                slow = mean(closes[index - 30:index]) if index >= 30 else mean(closes[index - 20:index])
                previous_fast = mean(closes[index - 11:index - 1])
                if fast > slow and closes[index - 1] <= previous_fast and closes[index] > fast:
                    indices.append(index)
            elif hypothesis == "IMPULSE_CONTINUATION":
                impulse = closes[index - 3] / closes[index - 8] - 1.0 if index >= 8 and closes[index - 8] > 0 else 0.0
                if impulse >= 0.05 and closes[index] > closes[index - 1]:
                    indices.append(index)
            elif hypothesis == "SHOCK_REVERSAL":
                if closes[index] / closes[index - 1] - 1.0 <= -0.04:
                    indices.append(index)
            elif hypothesis == "GAP_REVERSAL":
                if opens[index] / closes[index - 1] - 1.0 <= -0.03:
                    indices.append(index)
            elif hypothesis == "RANGE_BREAK":
                prior_high = max(highs[index - 10:index])
                prior_low = min(lows[index - 10:index])
                if prior_low > 0 and prior_high / prior_low - 1.0 <= 0.06 and closes[index] > prior_high:
                    indices.append(index)
            else:
                raise ValueError(f"Unsupported discovery hypothesis: {hypothesis}")
        return indices

    @classmethod
    def run(cls, candles: Sequence[Candle]) -> ConditionalDiscoveryResult:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        logger.warning("[V086 CONDITIONAL DISCOVERY START] candles=%d hypotheses=%d horizons=%s", len(ordered), len(cls.HYPOTHESES), cls.HORIZONS)
        if len(ordered) < cls.MIN_LOOKBACK + 1:
            return ConditionalDiscoveryResult(CONDITIONAL_DISCOVERY_VERSION, len(ordered), cls.MIN_OBSERVATIONS, ())

        baselines = {h: [v for i in range(len(ordered)) if (v := cls._forward_return(ordered, i, h)) is not None] for h in cls.HORIZONS}
        evidence: list[ConditionalDiscoveryEvidence] = []
        for hypothesis in cls.HYPOTHESES:
            indices = cls._event_indices(ordered, hypothesis)
            cells: list[ConditionalDiscoveryCell] = []
            for regime in ("Trend", "Momentum", "Range", "Unclear", "TRANSITION"):
                for volatility in cls.VOLATILITY_BUCKETS:
                    for direction in cls.DIRECTIONS:
                        matching = [i for i in indices if cls._volatility_bucket(ordered, i) == volatility and cls._direction(ordered, i) == direction]
                        regime_matching = []
                        for i in matching:
                            try:
                                if RegimeEngine.classify(list(ordered[: i + 1])).regime == regime:
                                    regime_matching.append(i)
                            except (ValueError, IndexError):
                                continue
                        for horizon in cls.HORIZONS:
                            values = [v for i in regime_matching if (v := cls._forward_return(ordered, i, horizon)) is not None]
                            baseline = baselines[horizon]
                            baseline_mean = mean(baseline) * 100.0 if baseline else 0.0
                            event_mean = mean(values) * 100.0 if values else 0.0
                            cells.append(ConditionalDiscoveryCell(hypothesis, regime, volatility, direction, horizon, len(values), event_mean, median(values) * 100.0 if values else 0.0, sum(v > 0 for v in values) / len(values) * 100.0 if values else 0.0, baseline_mean, event_mean - baseline_mean, len(values) >= cls.MIN_OBSERVATIONS))
            item = ConditionalDiscoveryEvidence(hypothesis, len(indices), tuple(cells))
            logger.warning("[V086 CONDITIONAL HYPOTHESIS] hypothesis=%s events=%d sufficient_cells=%d positive_excess_cells=%d", hypothesis, item.events, item.sufficient_cells, item.positive_excess_cells)
            evidence.append(item)
        return ConditionalDiscoveryResult(CONDITIONAL_DISCOVERY_VERSION, len(ordered), cls.MIN_OBSERVATIONS, tuple(evidence))


__all__ = ["CONDITIONAL_DISCOVERY_VERSION", "ConditionalDiscoveryCell", "ConditionalDiscoveryEvidence", "ConditionalDiscoveryResult", "ConditionalDiscoveryServiceV086"]
