from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MultipleTestingAssessmentV088:
    hypotheses_tested: int
    positive_hypotheses: int
    expected_false_positives_at_alpha: float
    false_discovery_rate_proxy_pct: float


class MultipleTestingControlV088:
    """Conservative discovery audit for large conditional search spaces.

    This first v0.8.8 layer is an audit metric, not a promotion gate. It makes
    the size of the search space explicit and reports the expected number of
    false positives under a simple null-rate approximation. It does not alter
    candidate status or production decisions.
    """

    @staticmethod
    def assess(p_values: Iterable[float], alpha: float = 0.05) -> MultipleTestingAssessmentV088:
        if not 0 < alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        values = tuple(float(value) for value in p_values)
        if any(value < 0 or value > 1 for value in values):
            raise ValueError("p-values must be between 0 and 1")
        positive = sum(value <= alpha for value in values)
        expected_false = len(values) * alpha
        fdr_proxy = (expected_false / positive * 100.0) if positive else 0.0
        return MultipleTestingAssessmentV088(
            hypotheses_tested=len(values),
            positive_hypotheses=positive,
            expected_false_positives_at_alpha=expected_false,
            false_discovery_rate_proxy_pct=min(fdr_proxy, 100.0),
        )


__all__ = ["MultipleTestingAssessmentV088", "MultipleTestingControlV088"]
