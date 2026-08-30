from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, median, pstdev
from typing import Iterable

from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryResult


@dataclass(frozen=True, slots=True)
class EvidenceAuditV086:
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
    dispersion_pct: float
    standard_error_pct: float
    effect_to_dispersion: float
    periods: int
    positive_periods: int
    negative_periods: int
    persistence_pct: float
    sufficient_sample: bool


class EvidenceAuditServiceV086:
    """Research-only evidence diagnostics; never changes strategy selection or QG."""

    @staticmethod
    def _period_returns(result: ConditionalDiscoveryResult, cell: ConditionalDiscoveryCell) -> list[float]:
        values = [
            item.forward_return(cell.horizon)
            for item in result.observations
            if item.hypothesis == cell.hypothesis
            and item.regime == cell.regime
            and item.volatility_bucket == cell.volatility_bucket
            and item.direction == cell.direction
        ]
        return [value for value in values if value is not None]

    @classmethod
    def audit_cell(cls, result: ConditionalDiscoveryResult, cell: ConditionalDiscoveryCell) -> EvidenceAuditV086:
        values = cls._period_returns(result, cell)
        dispersion = pstdev(values) if len(values) > 1 else 0.0
        se = dispersion / sqrt(len(values)) if values else 0.0
        # A period is represented by the calendar date of the observation. This is
        # deliberately coarse: it measures temporal recurrence, not independent samples.
        dates = {}
        for item in result.observations:
            if item.hypothesis != cell.hypothesis or item.regime != cell.regime or item.volatility_bucket != cell.volatility_bucket or item.direction != cell.direction:
                continue
            value = item.forward_return(cell.horizon)
            if value is None:
                continue
            day = getattr(item.timestamp, "date", lambda: item.timestamp)()
            dates.setdefault(day, []).append(value)
        period_values = [mean(items) for items in dates.values()]
        positive_periods = sum(value > 0 for value in period_values)
        negative_periods = sum(value < 0 for value in period_values)
        periods = len(period_values)
        return EvidenceAuditV086(
            hypothesis=cell.hypothesis,
            regime=cell.regime,
            volatility_bucket=cell.volatility_bucket,
            direction=cell.direction,
            horizon=cell.horizon,
            observations=len(values),
            mean_forward_return_pct=cell.mean_forward_return_pct,
            median_forward_return_pct=cell.median_forward_return_pct,
            win_rate_pct=cell.win_rate_pct,
            baseline_mean_return_pct=cell.baseline_mean_return_pct,
            excess_return_pct=cell.excess_return_pct,
            dispersion_pct=dispersion,
            standard_error_pct=se,
            effect_to_dispersion=(cell.excess_return_pct / dispersion) if dispersion else 0.0,
            periods=periods,
            positive_periods=positive_periods,
            negative_periods=negative_periods,
            persistence_pct=(positive_periods / periods * 100.0) if periods else 0.0,
            sufficient_sample=len(values) >= result.min_observations,
        )

    @classmethod
    def audit(cls, result: ConditionalDiscoveryResult) -> tuple[EvidenceAuditV086, ...]:
        audits = tuple(cls.audit_cell(result, cell) for evidence in result.evidence for cell in evidence.cells)
        return audits


__all__ = ["EvidenceAuditV086", "EvidenceAuditServiceV086"]
