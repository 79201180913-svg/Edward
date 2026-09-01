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
    RISK_GATE_FAILED = "RISK_GATE_FAILED"
    VALIDATION_REJECTED = "PATH_VALIDATION_REJECTED"
    MISSING_OPPORTUNITY = "OPPORTUNITY_UNAVAILABLE"
    MISSING_EV = "EV_UNAVAILABLE"
    MISSING_SCORE = "OPPORTUNITY_SCORE_UNAVAILABLE"
    LOW_SCORE = "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    LOW_CONFIDENCE = "CONFIDENCE_BELOW_THRESHOLD"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"


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
        hard_failures = {TradingPathDecisionReasonV012.RISK_GATE_FAILED.value, TradingPathDecisionReasonV012.VALIDATION_REJECTED.value}
        decision = TradingPathDecisionV012.PASS if any(r in hard_failures for r in reasons) else TradingPathDecisionV012.WAIT if reasons else TradingPathDecisionV012.BUY
        return TradingPathDecisionResultV012(decision=decision, current_state=TradingPathCurrentState.INVALID if decision is TradingPathDecisionV012.PASS else TradingPathCurrentState.WAIT if decision is TradingPathDecisionV012.WAIT else TradingPathCurrentState.ENTRY_READY, status=TradingPathAnalysisStatus.REJECTED if decision is TradingPathDecisionV012.PASS else TradingPathAnalysisStatus.VALIDATED if decision is TradingPathDecisionV012.WAIT else TradingPathAnalysisStatus.PROMOTABLE, reasons=tuple(reasons))

    @classmethod
    def apply(cls, analysis: TradingPathAnalysisV012, **kwargs: object) -> TradingPathAnalysisV012:
        result = cls.decide(analysis, **kwargs)
        return TradingPathAnalysisV012(
            instrument_uid=analysis.instrument_uid, ticker=analysis.ticker, strategy_family=analysis.strategy_family,
            hypothesis=analysis.hypothesis, regime=analysis.regime, volatility_bucket=analysis.volatility_bucket,
            direction=analysis.direction, horizon=analysis.horizon, evidence=analysis.evidence,
            validation=analysis.validation, market_context=analysis.market_context, opportunity=analysis.opportunity,
            current_state=result.current_state, decision=TradingPathDecision(result.decision.value), status=result.status,
            rank=analysis.rank,
        )


__all__ = ["TradingPathDecisionV012", "TradingPathDecisionReasonV012", "TradingPathDecisionResultV012", "TradingPathDecisionServiceV012"]
