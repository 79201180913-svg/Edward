from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryResult, ConditionalDiscoveryServiceV086
from edward.services.event_observation_v086 import HORIZONS, VOLATILITY_BUCKETS, DIRECTIONS
from edward.services.regime_engine_v08 import RegimeEngine


@dataclass(frozen=True, slots=True)
class CoverageAudit:
    hypothesis: str
    events: int
    by_regime: dict[str, int]
    by_volatility: dict[str, int]
    by_direction: dict[str, int]
    by_regime_volatility: dict[str, int]
    by_regime_direction: dict[str, int]
    by_volatility_direction: dict[str, int]
    by_full_condition: dict[str, int]
    sufficient_cells: int
    insufficient_cells: int
    sparsity_pct: float
    largest_condition_share_pct: float


class ConditionalDiscoveryCoverageV086:
    """Coverage audit over the observations already computed by Discovery."""

    @classmethod
    def from_result(cls, result: ConditionalDiscoveryResult) -> tuple[CoverageAudit, ...]:
        total_cells = len(RegimeEngine.REGIMES) * len(VOLATILITY_BUCKETS) * len(DIRECTIONS) * len(HORIZONS)
        audits: list[CoverageAudit] = []
        for evidence in result.evidence:
            events = tuple(item for item in result.observations if item.hypothesis == evidence.hypothesis)
            by_regime = Counter(item.regime for item in events)
            by_volatility = Counter(item.volatility_bucket for item in events)
            by_direction = Counter(item.direction for item in events)
            by_regime_volatility = Counter(f"{item.regime}|{item.volatility_bucket}" for item in events)
            by_regime_direction = Counter(f"{item.regime}|{item.direction}" for item in events)
            by_volatility_direction = Counter(f"{item.volatility_bucket}|{item.direction}" for item in events)
            by_full = Counter(f"{item.regime}|{item.volatility_bucket}|{item.direction}" for item in events)
            sufficient = evidence.sufficient_cells
            insufficient = total_cells - sufficient
            largest = max(by_full.values(), default=0)
            share = largest / len(events) * 100.0 if events else 0.0
            sparsity = insufficient / total_cells * 100.0 if total_cells else 0.0
            audits.append(CoverageAudit(
                hypothesis=evidence.hypothesis,
                events=len(events),
                by_regime=dict(by_regime),
                by_volatility=dict(by_volatility),
                by_direction=dict(by_direction),
                by_regime_volatility=dict(by_regime_volatility),
                by_regime_direction=dict(by_regime_direction),
                by_volatility_direction=dict(by_volatility_direction),
                by_full_condition=dict(by_full),
                sufficient_cells=sufficient,
                insufficient_cells=insufficient,
                sparsity_pct=round(sparsity, 2),
                largest_condition_share_pct=round(share, 2),
            ))
        return tuple(audits)

    @classmethod
    def run(cls, candles: Sequence[Candle]) -> tuple[CoverageAudit, ...]:
        """Compatibility wrapper; new callers should run Discovery once and use from_result."""
        return cls.from_result(ConditionalDiscoveryServiceV086.run(candles))


__all__ = ["CoverageAudit", "ConditionalDiscoveryCoverageV086"]
