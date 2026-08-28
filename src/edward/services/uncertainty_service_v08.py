from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Sequence


UNCERTAINTY_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class UncertaintyResult:
    expected_pct: float
    median_pct: float
    p10_pct: float
    p25_pct: float
    p75_pct: float
    p90_pct: float
    downside_pct: float
    upside_pct: float
    standard_deviation_pct: float
    width_pct: float
    observations: int
    version: str = UNCERTAINTY_VERSION


class UncertaintyService:
    """Describe the distribution of historical or simulated trade outcomes."""

    @staticmethod
    def _percentile(values: Sequence[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(float(value) for value in values)
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * percentile / 100.0
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    @classmethod
    def from_returns(cls, returns_pct: Sequence[float]) -> UncertaintyResult:
        values = tuple(float(value) for value in returns_pct)
        if not values:
            return UncertaintyResult(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
        p10 = cls._percentile(values, 10.0)
        p25 = cls._percentile(values, 25.0)
        median = cls._percentile(values, 50.0)
        p75 = cls._percentile(values, 75.0)
        p90 = cls._percentile(values, 90.0)
        return UncertaintyResult(
            expected_pct=mean(values),
            median_pct=median,
            p10_pct=p10,
            p25_pct=p25,
            p75_pct=p75,
            p90_pct=p90,
            downside_pct=min(0.0, p10),
            upside_pct=max(0.0, p90),
            standard_deviation_pct=pstdev(values) if len(values) > 1 else 0.0,
            width_pct=p90 - p10,
            observations=len(values),
        )


__all__ = ["UNCERTAINTY_VERSION", "UncertaintyResult", "UncertaintyService"]
