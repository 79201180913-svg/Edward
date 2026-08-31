from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist


@dataclass(frozen=True, slots=True)
class TradingPathMultipleTestingEvidenceV088:
    tests_count: int
    familywise_alpha: float
    adjusted_alpha: float
    critical_z: float
    adjusted_ci95_low_pct: float
    adjusted_ci95_high_pct: float

    @property
    def passes(self) -> bool:
        return self.adjusted_ci95_low_pct > 0.0


class TradingPathMultipleTestingServiceV088:
    """Conservative Bonferroni family-wise error control for path research."""

    @classmethod
    def evaluate(
        cls,
        *,
        mean_return_pct: float,
        standard_error_pct: float,
        tests_count: int,
        familywise_alpha: float = 0.05,
    ) -> TradingPathMultipleTestingEvidenceV088:
        tests = max(1, int(tests_count))
        alpha = min(max(float(familywise_alpha), 1e-12), 0.999999)
        adjusted_alpha = alpha / tests
        tail = adjusted_alpha / 2.0
        critical_z = NormalDist().inv_cdf(1.0 - tail)
        margin = critical_z * max(0.0, float(standard_error_pct))
        return TradingPathMultipleTestingEvidenceV088(
            tests_count=tests,
            familywise_alpha=alpha,
            adjusted_alpha=adjusted_alpha,
            critical_z=critical_z,
            adjusted_ci95_low_pct=float(mean_return_pct) - margin,
            adjusted_ci95_high_pct=float(mean_return_pct) + margin,
        )


__all__ = ["TradingPathMultipleTestingEvidenceV088", "TradingPathMultipleTestingServiceV088"]
