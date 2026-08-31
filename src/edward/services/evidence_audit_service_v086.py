from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryResult
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult


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


@dataclass(frozen=True, slots=True)
class WFAwareEvidenceAuditV086:
    hypothesis: str
    regime: str
    volatility_bucket: str
    direction: str
    horizon: int
    wf_windows: int
    positive_wf_windows: int
    negative_wf_windows: int
    wf_persistence_pct: float
    observations: int


class EvidenceAuditServiceV086:
    """Research-only evidence diagnostics; never changes discovery, WF or QG."""

    PERIOD_CANDLES = 60

    @staticmethod
    def _cell_values(result: ConditionalDiscoveryResult, cell: ConditionalDiscoveryCell) -> list[float]:
        values: list[float] = []
        for item in result.observations:
            if item.hypothesis != cell.hypothesis or item.regime != cell.regime or item.volatility_bucket != cell.volatility_bucket or item.direction != cell.direction:
                continue
            value = item.forward_return(cell.horizon)
            if value is not None:
                values.append(value)
        return values

    @classmethod
    def audit_cell(cls, result: ConditionalDiscoveryResult, cell: ConditionalDiscoveryCell) -> EvidenceAuditV086:
        values = cls._cell_values(result, cell)
        dispersion = pstdev(values) if len(values) > 1 else 0.0
        se = dispersion / sqrt(len(values)) if values else 0.0
        periods_values: dict[int, list[float]] = {}
        for item in result.observations:
            if item.hypothesis != cell.hypothesis or item.regime != cell.regime or item.volatility_bucket != cell.volatility_bucket or item.direction != cell.direction:
                continue
            value = item.forward_return(cell.horizon)
            if value is None:
                continue
            period = item.index // cls.PERIOD_CANDLES
            periods_values.setdefault(period, []).append(value)
        period_values = [mean(items) for items in periods_values.values()]
        positive_periods = sum(value > 0 for value in period_values)
        negative_periods = sum(value < 0 for value in period_values)
        periods = len(period_values)
        return EvidenceAuditV086(
            hypothesis=cell.hypothesis, regime=cell.regime, volatility_bucket=cell.volatility_bucket,
            direction=cell.direction, horizon=cell.horizon, observations=len(values),
            mean_forward_return_pct=cell.mean_forward_return_pct, median_forward_return_pct=cell.median_forward_return_pct,
            win_rate_pct=cell.win_rate_pct, baseline_mean_return_pct=cell.baseline_mean_return_pct,
            excess_return_pct=cell.excess_return_pct, dispersion_pct=dispersion, standard_error_pct=se,
            effect_to_dispersion=(cell.excess_return_pct / dispersion) if dispersion else 0.0,
            periods=periods, positive_periods=positive_periods, negative_periods=negative_periods,
            persistence_pct=(positive_periods / periods * 100.0) if periods else 0.0,
            sufficient_sample=len(values) >= result.min_observations,
        )

    @classmethod
    def audit(cls, result: ConditionalDiscoveryResult) -> tuple[EvidenceAuditV086, ...]:
        return tuple(cls.audit_cell(result, cell) for evidence in result.evidence for cell in evidence.cells)

    @staticmethod
    def _timestamp_index(candles: Sequence[Candle]) -> dict[object, int]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        return {candle.timestamp: index for index, candle in enumerate(ordered)}

    @classmethod
    def audit_wf(cls, result: ConditionalDiscoveryResult, wf_result: RobustWalkForwardResult, candles: Sequence[Candle]) -> tuple[WFAwareEvidenceAuditV086, ...]:
        """Measure conditional evidence recurrence inside actual WF test windows."""
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        timestamp_to_index = {candle.timestamp: index for index, candle in enumerate(ordered)}
        output: list[WFAwareEvidenceAuditV086] = []
        for evidence in result.evidence:
            for cell in evidence.cells:
                positive = negative = observations = 0
                for window in wf_result.windows:
                    start = timestamp_to_index.get(window.test_start)
                    end = timestamp_to_index.get(window.test_end)
                    if start is None or end is None:
                        continue
                    values: list[float] = []
                    for item in result.observations:
                        if item.hypothesis != cell.hypothesis or item.regime != cell.regime or item.volatility_bucket != cell.volatility_bucket or item.direction != cell.direction or not (start <= item.index <= end) or item.index + cell.horizon > end or item.index + cell.horizon >= len(ordered):
                            continue
                        value = item.forward_return(cell.horizon)
                        if value is not None:
                            values.append(value)
                    if not values:
                        continue
                    observations += len(values)
                    if mean(values) > 0:
                        positive += 1
                    else:
                        negative += 1
                total = positive + negative
                output.append(WFAwareEvidenceAuditV086(
                    hypothesis=cell.hypothesis, regime=cell.regime, volatility_bucket=cell.volatility_bucket,
                    direction=cell.direction, horizon=cell.horizon, wf_windows=total,
                    positive_wf_windows=positive, negative_wf_windows=negative,
                    wf_persistence_pct=positive / total * 100.0 if total else 0.0,
                    observations=observations,
                ))
        return tuple(output)


__all__ = ["EvidenceAuditV086", "WFAwareEvidenceAuditV086", "EvidenceAuditServiceV086"]
