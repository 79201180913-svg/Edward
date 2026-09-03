from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from edward.domain import TradingPathAnalysisStatus, TradingPathAnalysisV012, TradingPathCurrentState, TradingPathDecision


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
    MARKET_CONTEXT_UNAVAILABLE = "MARKET_CONTEXT_UNAVAILABLE"
    MARKET_CONTEXT_UNFAVORABLE = "MARKET_CONTEXT_UNFAVORABLE"


@dataclass(frozen=True, slots=True)
class TradingPathDecisionResultV012:
    decision: TradingPathDecisionV012
    current_state: TradingPathCurrentState
    status: TradingPathAnalysisStatus
    reasons: tuple[str, ...]


class TradingPathDecisionServiceV012:
    @staticmethod
    def decide(analysis: TradingPathAnalysisV012, *, minimum_opportunity_score: float = 70.0, minimum_confidence: float = 60.0) -> TradingPathDecisionResultV012:
        reasons: list[str] = []
        opportunity = analysis.opportunity
        validation = analysis.validation
        market_context = getattr(analysis, "market_context", None)
        if analysis.evidence is None:
            reasons.append("EVIDENCE_UNAVAILABLE")
        if validation is None:
            reasons.append("VALIDATION_UNAVAILABLE")
        else:
            promotion_status = getattr(validation, "promotion_status", None)
            if promotion_status == "REJECTED" or promotion_status == TradingPathAnalysisStatus.REJECTED.value:
                reasons.append("PATH_VALIDATION_REJECTED")
        if opportunity is None:
            reasons.append("OPPORTUNITY_UNAVAILABLE")
        else:
            if opportunity.risk_gate is False:
                reasons.append("RISK_GATE_FAILED")
            if opportunity.expected_value_pct is None:
                reasons.append("EV_UNAVAILABLE")
            if opportunity.score is None:
                reasons.append("OPPORTUNITY_SCORE_UNAVAILABLE")
            elif opportunity.score < minimum_opportunity_score:
                reasons.append("OPPORTUNITY_SCORE_BELOW_THRESHOLD")
            if opportunity.confidence is None:
                reasons.append("CONFIDENCE_UNAVAILABLE")
            elif opportunity.confidence < minimum_confidence:
                reasons.append("CONFIDENCE_BELOW_THRESHOLD")
        if market_context is not None:
            context_status = getattr(market_context, "context_status", None)
            regime_excess = getattr(market_context, "regime_excess_pct", None)
            market_excess = getattr(market_context, "market_excess_pct", None)
            has_context_data = any(
                value is not None
                for value in (
                    getattr(market_context, "benchmark_id", None),
                    getattr(market_context, "instrument_return_pct", None),
                    getattr(market_context, "instrument_baseline_return_pct", None),
                    getattr(market_context, "regime_baseline_return_pct", None),
                    getattr(market_context, "market_return_pct", None),
                    getattr(market_context, "instrument_excess_pct", None),
                    regime_excess,
                    market_excess,
                    getattr(market_context, "relative_strength_pct", None),
                    context_status,
                )
            )
            if has_context_data:
                if context_status != "FULL" or regime_excess is None or market_excess is None:
                    reasons.append("MARKET_CONTEXT_UNAVAILABLE")
                elif regime_excess <= 0.0 or market_excess <= 0.0:
                    reasons.append("MARKET_CONTEXT_UNFAVORABLE")
        hard_failures = {"RISK_GATE_FAILED", "PATH_VALIDATION_REJECTED"}
        if any(reason in hard_failures for reason in reasons):
            decision = TradingPathDecisionV012.PASS
            current_state = TradingPathCurrentState.INVALID
            status = TradingPathAnalysisStatus.REJECTED
        elif reasons:
            decision = TradingPathDecisionV012.WAIT
            current_state = TradingPathCurrentState.WAIT
            status = TradingPathAnalysisStatus.VALIDATED
        else:
            decision = TradingPathDecisionV012.BUY
            current_state = TradingPathCurrentState.ENTRY_READY
            status = TradingPathAnalysisStatus.PROMOTABLE
        return TradingPathDecisionResultV012(decision=decision, current_state=current_state, status=status, reasons=tuple(reasons))

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
