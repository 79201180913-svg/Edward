from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086
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
    """Auditable coverage statistics for the conditional research matrix."""

    @classmethod
    def run(cls, candles: Sequence[Candle]) -> tuple[CoverageAudit, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        audits: list[CoverageAudit] = []
        total_cells = len(RegimeEngine.REGIMES) * len(ConditionalDiscoveryServiceV086.VOLATILITY_BUCKETS) * len(ConditionalDiscoveryServiceV086.DIRECTIONS) * len(ConditionalDiscoveryServiceV086.HORIZONS)

        for hypothesis in ConditionalDiscoveryServiceV086.HYPOTHESES:
            events: list[tuple[int, str, str, str]] = []
            for index in ConditionalDiscoveryServiceV086._event_indices(ordered, hypothesis):
                regime = RegimeEngine.classify(ordered[: index + 1]).regime
                volatility = ConditionalDiscoveryServiceV086._volatility_bucket(ordered, index)
                direction = ConditionalDiscoveryServiceV086._direction(ordered, index)
                events.append((index, regime, volatility, direction))

            by_regime = Counter(r for _, r, _, _ in events)
            by_volatility = Counter(v for _, _, v, _ in events)
            by_direction = Counter(d for _, _, _, d in events)
            by_regime_volatility = Counter(f"{r}|{v}" for _, r, v, _ in events)
            by_regime_direction = Counter(f"{r}|{d}" for _, r, _, d in events)
            by_volatility_direction = Counter(f"{v}|{d}" for _, _, v, d in events)
            by_full = Counter(f"{r}|{v}|{d}" for _, r, v, d in events)

            # Every event contributes to each horizon cell. Sufficient-cell
            # accounting is based on the already calculated conditional result.
            result = ConditionalDiscoveryServiceV086.run(ordered)
            evidence = next(item for item in result.evidence if item.hypothesis == hypothesis)
            sufficient = evidence.sufficient_cells
            insufficient = total_cells - sufficient
            largest = max(by_full.values(), default=0)
            share = largest / len(events) * 100.0 if events else 0.0
            sparsity = insufficient / total_cells * 100.0 if total_cells else 0.0

            audit = CoverageAudit(
                hypothesis=hypothesis,
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
            )
            audits.append(audit)

        return tuple(audits)


__all__ = ["CoverageAudit", "ConditionalDiscoveryCoverageV086"]
