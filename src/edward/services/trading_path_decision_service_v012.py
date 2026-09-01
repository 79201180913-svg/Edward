from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathAnalysisV012,
    TradingPathCurrentState,
    TradingPathDecision,
)


class TradingPathDecisionV012(StrEnum):
    BUY = "buy"
    WAIT = "wait"
    PASS = "pass"


class TradingPathDecisionReasonV012(StrEnum):
    READY = "ready"
    RISK_GATE_FAILED = "risk_gate_failed"
    VALIDATION_REJECTED = "validation_rejected"
    MISSING_OPPORTUNITY = "missing_opportunity"
    MISSING_EV = "missing_ev"
    MISSING_SCORE = "missing_score"
    LOW_SCORE = "low_score"
    LOW_CONFIDENCE = "low_confidence"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"


@dataclass(frozen=True, slots=True)
class TradingPathDecisionResultV012:
    decision: TradingPathDecisionV012
    current_state: TradingPathCurrentState
    status: TradingPathAnalysisStatus
    reasons: tuple[str, ...]


class TradingPathDecisionServiceV012:
    """Resolve canonical path state without invoking an order/execution layer."""

    @staticmethod
    def decide(
        analysis: TradingPathAnalysisV012,
        *,
        minimum_opportunity_score: float = 70.0,
        minimum_confidence: float = 60.0,
    ) -> TradingPathDecisionResultV012:
        reasons: list[str] = []
        opportunity = analysis.opportunity
        validation = analysis.validation

        if analysis.evidence is None:
            reasons.append(TradingPathDecisionReasonV012.EVIDENCE_UNAVAILABLE.value)
        if validation is None:
            reasons.append("VALIDATION_UNAVAILABLE")
        elif validation.promotion_status == TradingPathAnalysisStatus.REJECTED.value:
            reasons.append(TradingPathDecisionReasonV012.VALIDATION_REJECTED.value)

        if opportunity is None:
            reasons.append(TradingPathDecisionReasonV012.MISSING_OPPORTUNITY.value)
        else:
            if opportunity.risk_gate is False:
                reasons.append(TradingPathDecisionReasonV012.RISK_GATE_FAILED.value)
            if opportunity.expected_value_pct is None:
                reasons.append(TradingPathDecisionReasonV012.MISSING_EV.value)
            if opportunity.score is None:
                reasons.append(TradingPathDecisionReasonV012.MISSING_SCORE.value)
            elif opportunity.score < minimum_opportunity_score:
                reasons.append(TradingPathDecisionReasonV012.LOW_SCORE.value)
            if opportunity.confidence is None:
                reasons.append(TradingPathDecisionReasonV012.LOW_CONFIDENCE.value)
            elif opportunity.confidence < minimum_confidence:
                reasons.append(TradingPathDecisionReasonV012.LOW_CONFIDENCE.value)

        hard_failures = {
            TradingPathDecisionReasonV012.RISK_GATE_FAILED.value,
            TradingPathDecisionReasonV012.VALIDATION_REJECTED.value,
        }
        if any(reason in hard_failures for reason in reasons):
            return TradingPathDecisionResultV012(
                decision=TradingPathDecisionV012.PASS,
                current_state=TradingPathCurrentState.INVALID,
                status=TradingPathAnalysisStatus.REJECTED,
                reasons=tuple(reasons),
            )
        if reasons:
            return TradingPathDecisionResultV012(
                decision=TradingPathDecisionV012.WAIT,
                current_state=TradingPathCurrentState.WAIT,
                status=TradingPathAnalysisStatus.VALIDATED,
                reasons=tuple(reasons),
            )
        return TradingPathDecisionResultV012(
            decision=TradingPathDecisionV012.BUY,
            current_state=TradingPathCurrentState.ENTRY_READY,
            status=TradingPathAnalysisStatus.PROMOTABLE,
            reasons=(),
        )

    @classmethod
    def apply(
        cls,
        analysis: TradingPathAnalysisV012,
        **kwargs: object,
    ) -> TradingPathAnalysisV012:
        result = cls.decide(analysis, **kwargs)
        return TradingPathAnalysisV012(
            instrument_uid=analysis.instrument_uid,
            ticker=analysis.ticker,
            strategy_family=analysis.strategy_family,
            hypothesis=analysis.hypothesis,
            regime=analysis.regime,
            volatility_bucket=analysis.volatility_bucket,
            direction=analysis.direction,
            horizon=analysis.horizon,
            evidence=analysis.evidence,
            validation=analysis.validation,
            market_context=analysis.market_context,
            opportunity=analysis.opportunity,
            current_state=result.current_state,
            decision=TradingPathDecision(result.decision.value),
            status=result.status,
            rank=analysis.rank,
        )


__all__ = [
    "TradingPathDecisionV012",
    "TradingPathDecisionReasonV012",
    "TradingPathDecisionResultV012",
    "TradingPathDecisionServiceV012",
]
