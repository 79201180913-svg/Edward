from __future__ import annotations

from dataclasses import dataclass


OPPORTUNITY_SCORE_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class OpportunityScoreResult:
    strategy_edge: float
    forecast_edge: float
    expected_value_score: float
    risk_score: float
    portfolio_impact_score: float
    regime_compatibility: float
    confidence: float
    score: float
    eligible: bool
    version: str = OPPORTUNITY_SCORE_VERSION


class OpportunityScoreService:
    """Build the v0.8 internal opportunity score without changing external contracts."""

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def calculate(
        cls,
        *,
        strategy_edge: float,
        forecast_edge: float,
        expected_value_score: float,
        risk_score: float,
        portfolio_impact_score: float,
        regime_compatibility: float,
        confidence: float,
        minimum_ev_score: float = 50.0,
        minimum_confidence: float = 50.0,
    ) -> OpportunityScoreResult:
        values = [
            cls._clamp(strategy_edge),
            cls._clamp(forecast_edge),
            cls._clamp(expected_value_score),
            cls._clamp(risk_score),
            cls._clamp(portfolio_impact_score),
            cls._clamp(regime_compatibility),
            cls._clamp(confidence),
        ]
        strategy, forecast, ev, risk, portfolio, regime, conf = values
        # Risk is represented as quality (100 = low risk / acceptable risk),
        # matching the positive-direction convention of the other components.
        score = (
            strategy * 0.20
            + forecast * 0.15
            + ev * 0.25
            + risk * 0.15
            + portfolio * 0.10
            + regime * 0.10
            + conf * 0.05
        )
        eligible = ev >= minimum_ev_score and conf >= minimum_confidence
        if not eligible:
            score = min(score, 59.99)
        return OpportunityScoreResult(*values, round(cls._clamp(score), 4), eligible)


__all__ = ["OPPORTUNITY_SCORE_VERSION", "OpportunityScoreResult", "OpportunityScoreService"]
