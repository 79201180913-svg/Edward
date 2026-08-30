from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryResult
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult


@dataclass(frozen=True, slots=True)
class EvidenceAudit:
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
    sufficient_sample: bool
    distinct_periods: int
    positive_periods: int
    negative_periods: int

    @property
    def persistence_pct(self) -> float:
        total = self.positive_periods + self.negative_periods
        return self.positive_periods / total * 100.0 if total else 0.0


@dataclass(frozen=True, slots=True)
class WFAwareEvidenceAudit:
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

    @staticmethod
    def _cell_values(result: ConditionalDiscoveryResult, cell: ConditionalDiscoveryCell):
        return tuple(
            item.forward_return(cell.horizon)
            for item in result.observations
            if item.hypothesis == cell.hypothesis
            and item.regime == cell.regime
            and item.volatility_bucket == cell.volatility_bucket
            and item.direction == cell.direction
            and item.forward_return(cell.horizon) is not None
        )

    @staticmethod
    def _period(index: int, period_size: int = 60) -> int:
        return index // period_size

    @classmethod
    def audit(cls, result: ConditionalDiscoveryResult) -> tuple[EvidenceAudit, ...]:
        audits: list[EvidenceAudit] = []
        for evidence in result.evidence:
            for cell in evidence.cells:
                values = cls._cell_values(result, cell)
                matching = [
                    item for item in result.observations
                    if item.hypothesis == cell.hypothesis
                    and item.regime == cell.regime
                    and item.volatility_bucket == cell.volatility_bucket
                    and item.direction == cell.direction
                    and item.forward_return(cell.horizon) is not None
                ]
                by_period: dict[int, list[float]] = {}
                for item, value in zip(matching, values):
                    by_period.setdefault(cls._period(item.index), []).append(value)
                period_means = [mean(period_values) for period_values in by_period.values() if period_values]
                positive_periods = sum(value > 0 for value in period_means)
                negative_periods = sum(value <= 0 for value in period_means)
                audits.append(EvidenceAudit(
                    hypothesis=cell.hypothesis,
                    regime=cell.regime,
                    volatility_bucket=cell.volatility_bucket,
                    direction=cell.direction,
                    horizon=cell.horizon,
                    observations=cell.observations,
                    mean_forward_return_pct=cell.mean_forward_return_pct,
                    median_forward_return_pct=cell.median_forward_return_pct,
                    win_rate_pct=cell.win_rate_pct,
                    baseline_mean_return_pct=cell.baseline_mean_return_pct,
                    excess_return_pct=cell.excess_return_pct,
                    dispersion_pct=0.0 if len(values) < 2 else (sum((value - mean(values)) ** 2 for value in values) / len(values)) ** 0.5,
                    sufficient_sample=cell.sufficient_sample,
                    distinct_periods=len(period_means),
                    positive_periods=positive_periods,
                    negative_periods=negative_periods,
                ))
        return tuple(audits)

    @staticmethod
    def _timestamp_index(candles: Sequence[Candle]) -> dict[object, int]:
        return {candle.timestamp: index for index, candle in enumerate(candles)}

    @classmethod
    def audit_wf(
        cls,
        result: ConditionalDiscoveryResult,
        wf_result: RobustWalkForwardResult,
        candles: Sequence[Candle],
    ) -> tuple[WFAwareEvidenceAudit, ...]:
        """Measure conditional evidence recurrence across actual WF test windows.

        An event counts only when it occurs inside a WF test interval and its
        forward-return horizon remains fully inside that same test interval. This
        prevents an event from borrowing observations from a later WF window.
        """
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        timestamp_to_index = cls._timestamp_index(ordered)
        output: list[WFAwareEvidenceAudit] = []
        for evidence in result.evidence:
            for cell in evidence.cells:
                positive = negative = observations = 0
                for window in wf_result.windows:
                    start = timestamp_to_index.get(window.test_start)
                    end = timestamp_to_index.get(window.test_end)
                    if start is None or end is None:
                        continue
                    values = []
                    for item in result.observations:
                        if item.hypothesis != cell.hypothesis or item.regime != cell.regime or item.volatility_bucket != cell.volatility_bucket or item.direction != cell.direction or not (start <= item.index <= end):
                            continue
                        horizon_end = item.index + cell.horizon
                        if horizon_end > end or horizon_end >= len(ordered):
                            continue
                        value = item.forward_return(cell.horizon)
                        if value is not None:
                            values.append(value)
                    if not values:
                        continue
                    observations += len(values)
                    window_mean = mean(values)
                    if window_mean > 0:
                        positive += 1
                    else:
                        negative += 1
                total = positive + negative
                output.append(WFAwareEvidenceAudit(
                    hypothesis=cell.hypothesis,
                    regime=cell.regime,
                    volatility_bucket=cell.volatility_bucket,
                    direction=cell.direction,
                    horizon=cell.horizon,
                    wf_windows=total,
                    positive_wf_windows=positive,
                    negative_wf_windows=negative,
                    wf_persistence_pct=positive / total * 100.0 if total else 0.0,
                    observations=observations,
                ))
        return tuple(output)


__all__ = ["EvidenceAudit", "WFAwareEvidenceAudit", "EvidenceAuditServiceV086"]
