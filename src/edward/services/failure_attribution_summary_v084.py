from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from edward.services.failure_attribution_v084 import FailureAttributionV084


@dataclass(frozen=True, slots=True)
class FailureAttributionSummaryV084:
    total_strategies: int
    passed_strategies: int
    failed_strategies: int
    primary_reason_counts: dict[str, int]
    dominant_failure_reason: str | None


class FailureAttributionSummaryServiceV084:
    @staticmethod
    def evaluate(items: Iterable[FailureAttributionV084]) -> FailureAttributionSummaryV084:
        values = tuple(items)
        counts = Counter(item.primary_reason for item in values if not item.passed)
        dominant = counts.most_common(1)[0][0] if counts else None
        return FailureAttributionSummaryV084(
            total_strategies=len(values),
            passed_strategies=sum(item.passed for item in values),
            failed_strategies=sum(not item.passed for item in values),
            primary_reason_counts=dict(counts),
            dominant_failure_reason=dominant,
        )


__all__ = ["FailureAttributionSummaryV084", "FailureAttributionSummaryServiceV084"]
