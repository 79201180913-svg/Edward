from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from edward.domain import TradingPathAnalysisV012


class TradingPathDecisionV012(str, Enum):
    BUY = "buy"
    WAIT = "wait"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class TradingPathDecisionResultV012:
    decision: TradingPathDecisionV012
    reasons: tuple[str, ...]


class TradingPathDecisionServiceV012:
    """Apply explicit hard gates after path Opportunity is calculated."""

    @staticmethod
    def decide(
        analysis: TradingPathAnalysisV012,
        *,
        minimum_opportunity_score: float = 70.0,
        minimum_confidence: float = 60.0,
    ) -> TradingPathDecisionResultV012:
        reasons: list[str] = []
        if analysis.evidence is None:
            reasons.append("EVIDENCE_UNAVAILABLE")
        if analysis.validation is None:
            reasons.append("VALIDATION_UNAVAILABLE")
        if analysis.opportunity is None:
            reasons.append("OPPORTUNITY_UNAVAILABLE")
        else:
            if analysis.opportunity.risk_gate is False:
                reasons.append("RISK_GATE_FAILED")
            if analysis.opportunity.expected_value_pct is None:
                reasons.append("EV_UNAVAILABLE")
            if analysis.opportunity.score is None:
                reasons.append("OPPORTUNITY_SCORE_UNAVAILABLE")
            elif analysis.opportunity.score < minimum_opportunity_score:
                reasons.append("OPPORTUNITY_SCORE_BELOW_THRESHOLD")
            if analysis.opportunity.confidence is None:
                reasons.append("CONFIDENCE_UNAVAILABLE")
            elif analysis.opportunity.confidence < minimum_confidence:
                reasons.append("CONFIDENCE_BELOW_THRESHOLD")

        validation = analysis.validation
        if validation is not None:
            if getattr(validation, "promotion_status", None) == "REJECTED":
                reasons.append("PATH_VALIDATION_REJECTED")
            if getattr(validation, "positive_oos_windows_pct", None) is not None and validation.positive_oos_windows_pct <= 0.0:
                reasons.append("NO_POSITIVE_OOS_WINDOWS")

        if reasons:
            # Missing/failed prerequisites are not equivalent to a tradeable negative signal.
            hard_failures = {"RISK_GATE_FAILED", "PATH_VALIDATION_REJECTED", "NO_POSITIVE_OOS_WINDOWS"}
            decision = TradingPathDecisionV012.PASS if any(reason in hard_failures for reason in reasons) else TradingPathDecisionV012.WAIT
        else:
            decision = TradingPathDecisionV012.BUY
        return TradingPathDecisionResultV012(decision=decision, reasons=tuple(reasons))


__all__ = ["TradingPathDecisionV012", "TradingPathDecisionResultV012", "TradingPathDecisionServiceV012"]
