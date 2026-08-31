from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.regime_engine_v08 import RegimeEngine

HORIZONS = (1, 3, 5, 10, 20)
MIN_LOOKBACK = 20
MIN_OBSERVATIONS = 8
HYPOTHESES = (
    "BREAKOUT_EXPANSION", "PULLBACK_RECLAIM", "IMPULSE_CONTINUATION",
    "SHOCK_REVERSAL", "GAP_REVERSAL", "RANGE_BREAK",
)
VOLATILITY_BUCKETS = ("Low", "Normal", "High")
DIRECTIONS = ("Positive", "Negative")


@dataclass(frozen=True, slots=True)
class EventObservationV086:
    hypothesis: str
    index: int
    timestamp: object
    regime: str
    volatility_bucket: str
    direction: str
    forward_returns_pct: tuple[tuple[int, float | None], ...]

    def forward_return(self, horizon: int) -> float | None:
        return dict(self.forward_returns_pct).get(horizon)


class EventObservationBuilderV086:
    """Create the single canonical event annotation set used by v0.8.6."""

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
        return [float(current.close) / float(previous.close) - 1.0 for previous, current in zip(candles, candles[1:]) if float(previous.close) > 0 and float(current.close) > 0]

    @classmethod
    def _volatility_bucket(cls, candles: Sequence[Candle], index: int) -> str:
        returns = cls._returns(candles[max(0, index - 20): index + 1])
        if len(returns) < 5:
            return "Normal"
        sigma = pstdev(returns)
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
        for index in range(MIN_LOOKBACK, len(candles)):
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
    def build(cls, candles: Sequence[Candle]) -> tuple[EventObservationV086, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        observations: list[EventObservationV086] = []
        for hypothesis in HYPOTHESES:
            for index in cls._event_indices(ordered, hypothesis):
                regime = RegimeEngine.classify(ordered[: index + 1]).regime
                volatility = cls._volatility_bucket(ordered, index)
                direction = cls._direction(ordered, index)
                forward_returns = tuple((horizon, cls._forward_return(ordered, index, horizon)) for horizon in HORIZONS)
                observations.append(EventObservationV086(
                    hypothesis=hypothesis,
                    index=index,
                    timestamp=ordered[index].timestamp,
                    regime=regime,
                    volatility_bucket=volatility,
                    direction=direction,
                    forward_returns_pct=tuple((h, value * 100.0 if value is not None else None) for h, value in forward_returns),
                ))
        return tuple(observations)


__all__ = ["DIRECTIONS", "HORIZONS", "HYPOTHESES", "MIN_LOOKBACK", "MIN_OBSERVATIONS", "VOLATILITY_BUCKETS", "EventObservationV086", "EventObservationBuilderV086"]
