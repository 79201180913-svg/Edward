from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Sequence


CONDITIONAL_DISCOVERY_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class ConditionalObservationV011:
    """Point-in-time observation used only for conditional research."""

    as_of: object
    condition: str
    future_return_pct: float


@dataclass(frozen=True, slots=True)
class ConditionalDiscoveryResultV011:
    condition: str
    observations: int
    mean_future_return_pct: float | None
    median_future_return_pct: float | None
    positive_rate_pct: float | None
    min_future_return_pct: float | None
    max_future_return_pct: float | None
    confidence_interval_95_pct: tuple[float, float] | None
    status: str
    version: str = CONDITIONAL_DISCOVERY_VERSION


class ConditionalMarketDiscoveryV011:
    """Find conditional historical effects without changing trading decisions.

    This is a research/evidence layer. It does not select strategies, modify
    scores, bypass Walk Forward, or change Quality Gate decisions.
    """

    MIN_OBSERVATIONS = 20

    @staticmethod
    def _median(values: Sequence[float]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2.0

    @classmethod
    def discover(
        cls,
        observations: Sequence[ConditionalObservationV011],
        *,
        condition: str,
        min_observations: int = MIN_OBSERVATIONS,
    ) -> ConditionalDiscoveryResultV011:
        if min_observations < 1:
            raise ValueError("min_observations must be >= 1")

        values = [
            float(item.future_return_pct)
            for item in observations
            if item.condition == condition
        ]
        if not values:
            return ConditionalDiscoveryResultV011(
                condition, 0, None, None, None, None, None, None, "UNAVAILABLE"
            )

        avg = mean(values)
        median = cls._median(values)
        positive_rate = sum(value > 0 for value in values) / len(values) * 100.0
        deviation = pstdev(values) if len(values) > 1 else 0.0
        if len(values) > 1:
            margin = 1.96 * deviation / sqrt(len(values))
            interval = (avg - margin, avg + margin)
        else:
            interval = None

        status = "SUFFICIENT" if len(values) >= min_observations else "INSUFFICIENT_SAMPLE"
        return ConditionalDiscoveryResultV011(
            condition=condition,
            observations=len(values),
            mean_future_return_pct=avg,
            median_future_return_pct=median,
            positive_rate_pct=positive_rate,
            min_future_return_pct=min(values),
            max_future_return_pct=max(values),
            confidence_interval_95_pct=interval,
            status=status,
        )

    @classmethod
    def discover_many(
        cls,
        observations: Sequence[ConditionalObservationV011],
        conditions: Sequence[str],
        *,
        min_observations: int = MIN_OBSERVATIONS,
    ) -> list[ConditionalDiscoveryResultV011]:
        return [
            cls.discover(
                observations,
                condition=condition,
                min_observations=min_observations,
            )
            for condition in conditions
        ]


__all__ = [
    "CONDITIONAL_DISCOVERY_VERSION",
    "ConditionalObservationV011",
    "ConditionalDiscoveryResultV011",
    "ConditionalMarketDiscoveryV011",
]
