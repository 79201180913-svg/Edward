from __future__ import annotations

from dataclasses import dataclass

from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisResult
from edward.services.risk_engine import RiskResult


@dataclass(frozen=True, slots=True)
class FundamentalRiskAdjustmentResult:
    risk_score: float
    score_delta: float
    position_multiplier: float
    blocked: bool
    reason_codes: tuple[str, ...] = ()


class FundamentalRiskAdjustmentServiceV082:
    """Conservative bridge between company fundamentals and trading risk.

    Fundamentals do not replace market/strategy risk. They can only adjust the
    risk interpretation of an otherwise valid risk result and can impose a
    conservative position-size multiplier when financial fragility is evident.
    """

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def apply(
        cls,
        risk: RiskResult,
        *,
        fundamental: FundamentalAnalysisResult,
    ) -> FundamentalRiskAdjustmentResult:
        if fundamental.status == "UNAVAILABLE" or fundamental.coverage <= 0:
            return FundamentalRiskAdjustmentResult(
                risk_score=risk.score,
                score_delta=0.0,
                position_multiplier=1.0,
                blocked=False,
                reason_codes=("FUNDAMENTAL_DATA_UNAVAILABLE",),
            )

        health = cls._clamp(fundamental.financial_health.score)
        quality = cls._clamp(fundamental.business_quality.score)
        cash = cls._clamp(fundamental.cash_generation.score)

        # Only material financial fragility changes trading risk. Strong quality
        # is confirmation, not a reason to make a risky trade safer.
        fragility = max(0.0, 50.0 - min(health, cash))
        score_delta = -fragility * 0.20
        adjusted = cls._clamp(risk.score + score_delta)

        if health < 35.0 or cash < 35.0:
            multiplier = 0.50
        elif health < 50.0 or cash < 50.0:
            multiplier = 0.75
        else:
            multiplier = 1.0

        reasons: list[str] = []
        if health < 50.0:
            reasons.append("FINANCIAL_HEALTH_WEAK")
        if cash < 50.0:
            reasons.append("CASH_GENERATION_WEAK")
        if quality >= 80.0 and multiplier == 1.0:
            reasons.append("FUNDAMENTAL_QUALITY_SUPPORT")

        return FundamentalRiskAdjustmentResult(
            risk_score=round(adjusted, 2),
            score_delta=round(score_delta, 2),
            position_multiplier=multiplier,
            blocked=False,
            reason_codes=tuple(reasons),
        )


__all__ = ["FundamentalRiskAdjustmentResult", "FundamentalRiskAdjustmentServiceV082"]
