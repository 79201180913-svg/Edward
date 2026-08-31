from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from edward.domain import TradingPathCandidate


@dataclass(frozen=True, slots=True)
class TradingPathOverlapEvidenceV088:
    candidate_key: str
    compared_candidates: int
    max_event_overlap_ratio: float
    max_holding_overlap_ratio: float

    @property
    def overlap_detected(self) -> bool:
        return self.max_event_overlap_ratio > 0.0 or self.max_holding_overlap_ratio > 0.0


class TradingPathOverlapAuditV088:
    """Measure dependence between candidate paths without declaring profitability."""

    @staticmethod
    def _key(candidate: TradingPathCandidate) -> str:
        rule = candidate.rule
        return "|".join((rule.hypothesis, rule.regime, rule.volatility_bucket, rule.direction, str(rule.horizon)))

    @staticmethod
    def _matches(candidate: TradingPathCandidate, observation) -> bool:
        rule = candidate.rule
        return (
            getattr(observation, "hypothesis", None) == rule.hypothesis
            and getattr(observation, "regime", None) == rule.regime
            and getattr(observation, "volatility_bucket", None) == rule.volatility_bucket
            and getattr(observation, "direction", None) == rule.direction
        )

    @classmethod
    def event_indices(cls, candidate: TradingPathCandidate, observations: Iterable[object]) -> frozenset[int]:
        return frozenset(int(observation.index) for observation in observations if cls._matches(candidate, observation))

    @staticmethod
    def holding_indices(event_indices: Iterable[int], horizon: int) -> frozenset[int]:
        return frozenset(index + offset for index in event_indices for offset in range(1, max(1, int(horizon)) + 1))

    @staticmethod
    def _ratio(left: frozenset[int], right: frozenset[int]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / min(len(left), len(right))

    @classmethod
    def audit(
        cls,
        candidate: TradingPathCandidate,
        candidates: Sequence[TradingPathCandidate],
        observations: Sequence[object],
    ) -> TradingPathOverlapEvidenceV088:
        own_events = cls.event_indices(candidate, observations)
        own_holding = cls.holding_indices(own_events, candidate.rule.horizon)
        max_event = 0.0
        max_holding = 0.0
        compared = 0
        for other in candidates:
            if other is candidate:
                continue
            compared += 1
            other_events = cls.event_indices(other, observations)
            other_holding = cls.holding_indices(other_events, other.rule.horizon)
            max_event = max(max_event, cls._ratio(own_events, other_events))
            max_holding = max(max_holding, cls._ratio(own_holding, other_holding))
        return TradingPathOverlapEvidenceV088(
            candidate_key=cls._key(candidate),
            compared_candidates=compared,
            max_event_overlap_ratio=max_event,
            max_holding_overlap_ratio=max_holding,
        )


__all__ = ["TradingPathOverlapEvidenceV088", "TradingPathOverlapAuditV088"]
