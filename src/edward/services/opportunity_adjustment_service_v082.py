from __future__ import annotations

from dataclasses import dataclass, replace

from edward.services.decision_engine import OpportunityContext
from edward.services.entry_quality_service_v082 import EntryQualityResult
from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisResult
from edward.services.opportunity_engine import OpportunityResult


@dataclass(frozen=True, slots=True)
class OpportunityAdjustmentResult:
    opportunity: OpportunityResult
    score_delta: float
    fundamental_support: float
    entry_quality_score: float
    blocked: bool
    reason_codes: tuple[str, ...] = ()


class OpportunityAdjustmentServiceV082:
    """Applies conservative v0.8.2 evidence adjustments to an existing opportunity.

    Fundamentals are asymmetric evidence: strong fundamentals may confirm an already
    valid entry, but cannot manufacture one. Weak fundamentals may reduce an
    opportunity when they conflict with an otherwise valid trade. Entry Quality can
    hard-block the entry independently of the opportunity score.
    """

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def apply(
        cls,
        opportunity: OpportunityResult,
        *,
        fundamental: FundamentalAnalysisResult,
        entry_quality: EntryQualityResult,
    ) -> OpportunityAdjustmentResult:
        fundamental_score = cls._clamp(fundamental.overall_score)
        entry_score = cls._clamp(entry_quality.score)

        # Positive fundamentals are confirmation only. Negative fundamentals can
        # penalize a trade more than positive fundamentals can boost it.
        if entry_quality.entry_signal:
            support_delta = (fundamental_score - 50.0) * 0.10
            if fundamental_score < 40.0:
                support_delta = (fundamental_score - 50.0) * 0.20
        else:
            support_delta = 0.0

        adjusted_score = cls._clamp(opportunity.score + support_delta)
        blocked = entry_quality.entry_blocked or not entry_quality.entry_signal
        context = replace(
            opportunity.context,
            opportunity_score=adjusted_score,
            entry_ok=opportunity.entry_signal and entry_quality.entry_signal,
        )
        reasons: list[str] = []
        if entry_quality.entry_blocked:
            reasons.append(entry_quality.block_reason or "ENTRY_BLOCKED")
        elif not entry_quality.entry_signal:
            reasons.append("ENTRY_NOT_CONFIRMED")
        if fundamental_score >= 70.0 and entry_quality.entry_signal:
            reasons.append("FUNDAMENTAL_SUPPORT")
        elif fundamental_score < 40.0 and entry_quality.entry_signal:
            reasons.append("FUNDAMENTAL_CONFLICT")

        explanation = (
            f"{opportunity.explanation} v0.8.2 Fundamental={fundamental_score:.1f}, "
            f"EntryQuality={entry_score:.1f}, adjustment={support_delta:+.2f}."
        )
        adjusted = OpportunityResult(
            context,
            adjusted_score,
            opportunity.entry_signal and entry_quality.entry_signal,
            opportunity.market_regime_compatible,
            explanation,
            opportunity.risk,
        )
        return OpportunityAdjustmentResult(
            adjusted,
            round(support_delta, 2),
            fundamental_score,
            entry_score,
            blocked,
            tuple(reasons),
        )


__all__ = ["OpportunityAdjustmentResult", "OpportunityAdjustmentServiceV082"]
