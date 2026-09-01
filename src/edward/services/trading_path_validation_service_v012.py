from __future__ import annotations

import logging
from dataclasses import dataclass

from edward.domain import TradingPathCandidate, TradingPathValidationSummary

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TradingPathValidationResultV012:
    candidate: TradingPathCandidate
    validation: TradingPathValidationSummary
    passed: bool


class TradingPathValidationServiceV012:
    """Validate a discovered path using existing path-level evidence only.

    This stage deliberately does not make a trading decision. Full historical
    walk-forward execution will be attached in the subsequent integration stage.
    """

    @staticmethod
    def validate(
        candidate: TradingPathCandidate,
        *,
        wf_persistence_pct: float | None = None,
        robustness_score: float | None = None,
        positive_oos_windows_pct: float | None = None,
        statistical_valid: bool | None = None,
        overlap_valid: bool | None = None,
        multiple_testing_valid: bool | None = None,
        promotion_status: str | None = None,
    ) -> TradingPathValidationResultV012:
        validation = TradingPathValidationSummary(
            wf_persistence_pct=wf_persistence_pct,
            robustness_score=robustness_score,
            positive_oos_windows_pct=positive_oos_windows_pct,
            statistical_valid=statistical_valid,
            overlap_valid=overlap_valid,
            multiple_testing_valid=multiple_testing_valid,
            promotion_status=promotion_status,
        )
        explicit_checks = [
            value for value in (statistical_valid, overlap_valid, multiple_testing_valid)
            if value is not None
        ]
        passed = candidate.evidence.sufficient_sample and candidate.evidence.excess_return_pct > 0.0 and all(explicit_checks)
        logger.warning(
            "[V012 PATH VALIDATION] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d N=%d excess=%.6f wf_persistence=%s robustness=%s positive_oos=%s statistical=%s overlap=%s multiple_testing=%s promotion=%s passed=%s",
            candidate.rule.ticker,
            candidate.rule.hypothesis,
            candidate.rule.regime,
            candidate.rule.volatility_bucket,
            candidate.rule.direction,
            candidate.rule.horizon,
            candidate.evidence.observations,
            candidate.evidence.excess_return_pct,
            wf_persistence_pct,
            robustness_score,
            positive_oos_windows_pct,
            statistical_valid,
            overlap_valid,
            multiple_testing_valid,
            promotion_status,
            passed,
        )
        return TradingPathValidationResultV012(candidate=candidate, validation=validation, passed=passed)


__all__ = ["TradingPathValidationResultV012", "TradingPathValidationServiceV012"]
