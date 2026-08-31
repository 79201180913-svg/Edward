from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from edward.services.event_observation_v086 import EventObservationV086


@dataclass(frozen=True, slots=True)
class EventOverlapPairV088:
    left_hypothesis: str
    right_hypothesis: str
    overlap_count: int


@dataclass(frozen=True, slots=True)
class EventOverlapAuditResultV088:
    total_observations: int
    unique_event_indices: int
    overlap_count: int
    pairwise_overlaps: tuple[EventOverlapPairV088, ...]


class EventOverlapAuditV088:
    """Audit overlap among canonical v0.8.6 event observations.

    This is diagnostic only: it does not alter discovery, WF, Quality Gate,
    recommendation, or execution behavior.
    """

    @staticmethod
    def run(observations: Sequence[EventObservationV086]) -> EventOverlapAuditResultV088:
        ordered = tuple(observations)
        event_keys = {(item.timestamp, item.index) for item in ordered}
        by_hypothesis = {}
        for item in ordered:
            by_hypothesis.setdefault(item.hypothesis, set()).add((item.timestamp, item.index))

        pairs: list[EventOverlapPairV088] = []
        for left, right in combinations(sorted(by_hypothesis), 2):
            overlap = len(by_hypothesis[left] & by_hypothesis[right])
            if overlap:
                pairs.append(EventOverlapPairV088(left, right, overlap))

        return EventOverlapAuditResultV088(
            total_observations=len(ordered),
            unique_event_indices=len(event_keys),
            overlap_count=len(ordered) - len(event_keys),
            pairwise_overlaps=tuple(pairs),
        )


__all__ = [
    "EventOverlapAuditV088",
    "EventOverlapAuditResultV088",
    "EventOverlapPairV088",
]
