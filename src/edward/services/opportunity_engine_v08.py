from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.decision_engine import OpportunityContext
from edward.services.opportunity_engine import OpportunityResult
from edward.services.analysis_service import AnalysisResult, StrategyResult, AnalysisService
from edward.services.risk_engine import RiskEngine
from edward.services.expected_value_engine_v08 import ExpectedValueResult
from edward.services.portfolio_impact_service_v08 import PortfolioImpactResult
from edward.services.regime_engine_v08 import RegimeEngine


OPPORTUNITY_V08_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class OpportunityScoreV08:
    strategy_edge: float
    robustness: float
    regime_compatibility: float
    expected_value: float
    risk_score: float
    portfolio_impact: float
    confidence: float
    score: float
    version: str = OPPORTUNITY_V08_VERSION


class OpportunityEngineV08:
    """Internal v0.8 scorer that returns the existing OpportunityResult contract."""

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def score(
        cls,
        *,
        analysis: AnalysisResult,
        strategy_result: StrategyResult,
        candles: list[Any],
        expected_value: ExpectedValueResult,
        portfolio_impact: PortfolioImpactResult,
        robustness_score: float | None = None,
        forecast_quality_score: float | None = None,
        confidence_score: float | None = None,
    ) -> OpportunityScoreV08:
        risk = RiskEngine.evaluate(
            strategy_result=strategy_result,
            candles=candles,
            profile=analysis.profile,
        )
        regime = RegimeEngine.classify(candles)
        regime_score = RegimeEngine.compatibility(regime.regime, strategy_result.strategy)
        entry_signal = AnalysisService._signal(
            strategy_result.strategy,
            candles,
            strategy_result.parameters,
            len(candles) - 1,
        )
        strategy_edge = cls._clamp(strategy_result.score)
        robustness = cls._clamp(robustness_score if robustness_score is not None else strategy_result.stability)
        ev_score = cls._clamp(50.0 + expected_value.expected_value_pct * 8.0)
        risk_score = cls._clamp(risk.score)
        portfolio_score = cls._clamp(portfolio_impact.portfolio_impact_score)
        forecast_score = cls._clamp(forecast_quality_score if forecast_quality_score is not None else 50.0)
        confidence = cls._clamp(confidence_score if confidence_score is not None else forecast_score)

        entry_component = 100.0 if entry_signal else 35.0
        score = round(
            strategy_edge * 0.20
            + robustness * 0.15
            + regime_score * 0.10
            + ev_score * 0.20
            + risk_score * 0.15
            + portfolio_score * 0.10
            + confidence * 0.10,
            2,
        )
        # Entry readiness remains a hard contextual gate rather than an eighth
        # additive score component, preserving the existing OpportunityResult API.
        if not entry_signal:
            score = round(score * 0.85 + entry_component * 0.15, 2)
        return OpportunityScoreV08(
            strategy_edge, robustness, regime_score, ev_score, risk_score,
            portfolio_score, confidence, cls._clamp(score),
        )

    @classmethod
    def evaluate(
        cls,
        *,
        analysis: AnalysisResult,
        candles: list[Any],
        strategy_result: StrategyResult | None,
        expected_value: ExpectedValueResult,
        portfolio_impact: PortfolioImpactResult,
        robustness_score: float | None = None,
        forecast_quality_score: float | None = None,
        confidence_score: float | None = None,
    ) -> OpportunityResult:
        if strategy_result is None:
            context = OpportunityContext(
                opportunity_score=0.0,
                entry_ok=False,
                risk_ok=False,
                strategy_ok=False,
                market_regime_compatible=False,
                critical_risk=True,
            )
            return OpportunityResult(context, 0.0, False, False, "Приемлемая стратегия отсутствует.", None)

        risk = RiskEngine.evaluate(
            strategy_result=strategy_result,
            candles=candles,
            profile=analysis.profile,
        )
        entry_signal = AnalysisService._signal(
            strategy_result.strategy,
            candles,
            strategy_result.parameters,
            len(candles) - 1,
        )
        regime = RegimeEngine.classify(candles)
        market_ok = RegimeEngine.compatibility(regime.regime, strategy_result.strategy) >= 60.0
        scored = cls.score(
            analysis=analysis,
            strategy_result=strategy_result,
            candles=candles,
            expected_value=expected_value,
            portfolio_impact=portfolio_impact,
            robustness_score=robustness_score,
            forecast_quality_score=forecast_quality_score,
            confidence_score=confidence_score,
        )
        strategy_ok = strategy_result.quality_gate and expected_value.expected_value_pct > 0.0
        risk_ok = risk.gate and not risk.critical and portfolio_impact.portfolio_impact_score >= 0.0
        context = OpportunityContext(
            opportunity_score=scored.score,
            entry_ok=entry_signal,
            risk_ok=risk_ok,
            strategy_ok=strategy_ok,
            market_regime_compatible=market_ok,
            critical_risk=risk.critical,
        )
        explanation = (
            f"v0.8 StrategyEdge={scored.strategy_edge:.1f}, robustness={scored.robustness:.1f}, "
            f"regime={scored.regime_compatibility:.1f}, EV={expected_value.expected_value_pct:.2f}%, "
            f"risk={scored.risk_score:.1f}, portfolio={scored.portfolio_impact:.1f}, "
            f"confidence={scored.confidence:.1f}."
        )
        return OpportunityResult(context, scored.score, entry_signal, market_ok, explanation, risk)


__all__ = ["OPPORTUNITY_V08_VERSION", "OpportunityScoreV08", "OpportunityEngineV08"]
