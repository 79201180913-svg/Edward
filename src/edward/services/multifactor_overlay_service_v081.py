from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.multifactor_analysis_service_v081 import MultiFactorResult

MULTIFACTOR_OVERLAY_VERSION = "0.8.1"


@dataclass(frozen=True, slots=True)
class MultiFactorOverlayResult:
    base_opportunity_score: float
    adjusted_opportunity_score: float
    base_confidence: float
    adjusted_confidence: float
    entry_quality_score: float
    risk_adjustment: float
    evidence_score: float
    evidence_reliability: float
    conflict_penalty: float
    decision_blocked: bool
    block_reason: str | None
    explanation: str
    version: str = MULTIFACTOR_OVERLAY_VERSION


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


class MultiFactorOverlayServiceV081:
    """Apply v0.8.1 evidence to v0.8 outputs without changing public contracts."""

    @classmethod
    def apply(cls, pipeline: AnalysisPipelineV08Result, factors: MultiFactorResult) -> tuple[AnalysisPipelineV08Result, MultiFactorOverlayResult]:
        base_score = float(pipeline.opportunity.score)
        base_confidence = float(pipeline.confidence.overall_confidence) if pipeline.confidence is not None else 0.0

        positive_quality = (
            factors.fundamentals.quality_score * 0.18
            + factors.microstructure.entry_quality_score * 0.15
            + (factors.volume_pressure.accumulation_score if factors.volume_pressure.evidence.available else 50.0) * 0.08
            + factors.signals.evidence.quality * 0.10
            + factors.dividends.evidence.quality * 0.05
            + factors.insider.evidence.quality * 0.05
            + factors.session.quality_score * 0.08
            + factors.portfolio.evidence.quality * 0.08
        ) / 0.77
        event_penalty = factors.event_risk.event_risk_score * 0.12
        instrument_penalty = max(0.0, factors.instrument_risk.risk_score - 50.0) * 0.10
        conflict_penalty = factors.conflict_penalty * 0.50
        reliability_discount = max(0.0, 60.0 - factors.aggregate_reliability_score) * 0.10

        adjustment = (positive_quality - 50.0) * 0.30 - event_penalty - instrument_penalty - conflict_penalty - reliability_discount
        adjusted_score = _clamp(base_score + adjustment)

        entry_quality = _clamp(
            pipeline.opportunity.entry_signal * 100.0 * 0.45
            + factors.microstructure.entry_quality_score * 0.35
            + (factors.volume_pressure.accumulation_score if factors.volume_pressure.evidence.available else 50.0) * 0.10
            + factors.session.quality_score * 0.10
        )
        risk_adjustment = _clamp(50.0 + (factors.instrument_risk.risk_score - 50.0) * 0.7 - factors.event_risk.event_risk_score * 0.25)

        confidence_delta = (factors.aggregate_reliability_score - 50.0) * 0.12 - factors.conflict_penalty * 0.50
        if not factors.session.is_execution_allowed:
            confidence_delta -= 10.0
        adjusted_confidence = _clamp(base_confidence + confidence_delta)

        blocked = False
        block_reason = None
        if factors.session.session == "CLEARING":
            blocked = True
            block_reason = "TRADING_SESSION_BLOCK"
        elif factors.instrument_risk.evidence.available and factors.instrument_risk.risk_score >= 90.0:
            blocked = True
            block_reason = "INSTRUMENT_RISK_TOO_HIGH"
        elif factors.event_risk.event_risk_score >= 95.0:
            blocked = True
            block_reason = "CORPORATE_EVENT_RISK"

        if blocked:
            adjusted_score = min(adjusted_score, 44.9)

        explanation = (
            f"v0.8.1 evidence={factors.aggregate_evidence_score:.1f}, reliability="
            f"{factors.aggregate_reliability_score:.1f}, conflict_penalty={factors.conflict_penalty:.1f}; "
            f"fundamental={factors.fundamentals.evidence.direction}, microstructure={factors.microstructure.evidence.direction}, "
            f"event_risk={factors.event_risk.event_risk_score:.1f}, session={factors.session.session}."
        )

        adjusted_opportunity = replace(
            pipeline.opportunity,
            score=round(adjusted_score, 2),
            explanation=f"{pipeline.opportunity.explanation} {explanation}",
        )
        adjusted_pipeline = replace(pipeline, opportunity=adjusted_opportunity)
        return adjusted_pipeline, MultiFactorOverlayResult(
            base_opportunity_score=base_score,
            adjusted_opportunity_score=round(adjusted_score, 2),
            base_confidence=base_confidence,
            adjusted_confidence=round(adjusted_confidence, 2),
            entry_quality_score=round(entry_quality, 2),
            risk_adjustment=round(risk_adjustment, 2),
            evidence_score=round(factors.aggregate_evidence_score, 2),
            evidence_reliability=round(factors.aggregate_reliability_score, 2),
            conflict_penalty=round(factors.conflict_penalty, 2),
            decision_blocked=blocked,
            block_reason=block_reason,
            explanation=explanation,
        )


@dataclass(frozen=True, slots=True)
class PointInTimeViolation:
    source: str
    available_at: datetime
    analysis_at: datetime
    identifier: str | None = None


class PointInTimeGuardV081:
    @staticmethod
    def validate(*, source: str, available_at: datetime, analysis_at: datetime, identifier: str | None = None) -> PointInTimeViolation | None:
        if available_at > analysis_at:
            return PointInTimeViolation(source, available_at, analysis_at, identifier)
        return None

    @classmethod
    def filter_visible(cls, *, records, analysis_at: datetime, source: str):
        visible = []
        violations = []
        for record in records:
            available_at = getattr(record, "created_at", None) if not isinstance(record, dict) else record.get("created_at")
            if available_at is None:
                visible.append(record)
                continue
            if isinstance(available_at, str):
                available_at = datetime.fromisoformat(available_at.replace("Z", "+00:00"))
            violation = cls.validate(source=source, available_at=available_at, analysis_at=analysis_at)
            if violation:
                violations.append(record)
            else:
                visible.append(record)
        return tuple(visible), tuple(violations)


__all__ = ["MULTIFACTOR_OVERLAY_VERSION", "MultiFactorOverlayResult", "MultiFactorOverlayServiceV081", "PointInTimeViolation", "PointInTimeGuardV081"]
