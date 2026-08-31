from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from edward.services.trading_path_multiple_testing_v088 import TradingPathMultipleTestingEvidenceV088
from edward.services.trading_path_overlap_audit_v088 import TradingPathOverlapEvidenceV088
from edward.services.trading_path_statistical_validation_v088 import TradingPathStatisticalEvidenceV088


@dataclass(frozen=True, slots=True)
class TradingPathPromotionEvidenceV088:
    statistical: TradingPathStatisticalEvidenceV088
    multiple_testing: TradingPathMultipleTestingEvidenceV088
    overlap: TradingPathOverlapEvidenceV088
    temporal_stable: bool
    economic_pass: bool

    @property
    def passes(self) -> bool:
        return (
            self.economic_pass
            and self.statistical.positive_mean
            and self.statistical.ci95_low_pct > 0.0
            and self.temporal_stable
            and self.overlap.max_event_overlap_ratio <= 0.0
            and self.overlap.max_holding_overlap_ratio <= 0.0
            and self.multiple_testing.passes
        )

    def reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.economic_pass:
            reasons.append("ECONOMIC_VALIDATION_FAILED")
        if not self.statistical.positive_mean:
            reasons.append("NON_POSITIVE_MEAN")
        if self.statistical.ci95_low_pct <= 0.0:
            reasons.append("CI95_NOT_ABOVE_ZERO")
        if not self.temporal_stable:
            reasons.append("TEMPORAL_INSTABILITY")
        if self.overlap.max_event_overlap_ratio > 0.0:
            reasons.append("EVENT_OVERLAP")
        if self.overlap.max_holding_overlap_ratio > 0.0:
            reasons.append("HOLDING_OVERLAP")
        if not self.multiple_testing.passes:
            reasons.append("MULTIPLE_TESTING_FAILED")
        return tuple(reasons)


class TradingPathPromotionEvidenceServiceV088:
    @staticmethod
    def build(
        *,
        statistical: TradingPathStatisticalEvidenceV088,
        multiple_testing: TradingPathMultipleTestingEvidenceV088,
        overlap: TradingPathOverlapEvidenceV088,
        temporal_stable: bool,
        economic_pass: bool,
    ) -> TradingPathPromotionEvidenceV088:
        return TradingPathPromotionEvidenceV088(
            statistical=statistical,
            multiple_testing=multiple_testing,
            overlap=overlap,
            temporal_stable=bool(temporal_stable),
            economic_pass=bool(economic_pass),
        )


__all__ = ["TradingPathPromotionEvidenceV088", "TradingPathPromotionEvidenceServiceV088"]
