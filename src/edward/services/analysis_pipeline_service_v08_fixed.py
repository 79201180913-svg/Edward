from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.confidence_calibration_v08 import calculate_confidence
from edward.services.confidence_service_v08 import ConfidenceResult
from edward.services.expected_value_engine_v08 import ExpectedValueEngine, ExpectedValueResult
from edward.services.forecast_quality_adapter_v08 import ForecastQualityAdapterV08
from edward.services.opportunity_engine import OpportunityResult
from edward.services.opportunity_engine_v08 import OpportunityEngineV08
from edward.services.portfolio_impact_service_v08 import PortfolioImpactResult, PortfolioImpactService
from edward.services.regime_confidence_v08 import cap_regime_confidence
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.research_backtest_service_v08 import ResearchBacktestService

ANALYSIS_PIPELINE_V08_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class AnalysisPipelineV08Result:
    analysis: AnalysisResult
    opportunity: OpportunityResult
    expected_value: ExpectedValueResult
    portfolio_impact: PortfolioImpactResult
    forecast_quality_score: float | None = None
    regime_confidence: float | None = None
    evidence_strategy: str | None = None
    portfolio_context_available: bool = False
    confidence: ConfidenceResult | None = None
    version: str = ANALYSIS_PIPELINE_V08_VERSION


class AnalysisPipelineServiceV08:
    """Corrected v0.8 pipeline facade with stable result shape."""

    def __init__(self, *, analysis_service: AnalysisServiceV08 | None = None) -> None:
        self.analysis_service = analysis_service or AnalysisServiceV08()
        self.forecast_quality = ForecastQualityAdapterV08()

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return [
            float(current.close) / float(previous.close) - 1.0
            for previous, current in zip(candles, candles[1:])
            if float(previous.close) > 0 and float(current.close) > 0
        ]

    @staticmethod
    def _empty_portfolio() -> PortfolioImpactResult:
        return PortfolioImpactResult(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def _portfolio_confidence(impact: PortfolioImpactResult, available: bool) -> float:
        if not available:
            return 0.0
        return max(
            0.0,
            min(
                100.0,
                70.0 + impact.diversification_benefit_pct * 5.0 - max(0.0, impact.marginal_risk_pct) * 5.0,
            ),
        )

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
        portfolio_weights: Mapping[str, float] | None = None,
        portfolio_returns: Mapping[str, Sequence[float]] | None = None,
        candidate_weight: float = 0.0,
        concentration_penalty_pct: float = 0.0,
    ) -> AnalysisPipelineV08Result:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        analysis = self.analysis_service.analyze(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=ordered,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
        )
        evidence_strategy_result = max(analysis.strategies, key=lambda item: item.score) if analysis.strategies else None
        evidence_strategy = evidence_strategy_result.strategy if evidence_strategy_result else None
        raw_regime = RegimeEngine.classify(ordered)
        regime_confidence = cap_regime_confidence(raw_regime.confidence)
        forecast_quality_score = None
        try:
            forecast_quality_score = self.forecast_quality.evaluate(
                candles=ordered,
                horizons=(1, 5, 20),
            ).overall_quality_score
        except ValueError:
            pass

        if evidence_strategy_result is None:
            ev = ExpectedValueEngine.from_returns(())
            impact = self._empty_portfolio()
            confidence = calculate_confidence(
                strategy_quality=0.0,
                forecast_quality=forecast_quality_score or 0.0,
                regime_confidence=regime_confidence,
                portfolio_confidence=0.0,
                observations=0,
            )
            opportunity = OpportunityEngineV08.evaluate(
                analysis=analysis,
                candles=ordered,
                strategy_result=None,
                expected_value=ev,
                portfolio_impact=impact,
                confidence_score=confidence.overall_confidence,
            )
            return AnalysisPipelineV08Result(
                analysis, opportunity, ev, impact,
                forecast_quality_score, regime_confidence, None, False, confidence,
            )

        backtest = ResearchBacktestService.run_simple_strategy(
            candles=ordered,
            strategy=evidence_strategy_result.strategy,
            parameters=evidence_strategy_result.parameters,
            costs=self.analysis_service.costs,
        )
        ev = ExpectedValueEngine.from_trades(backtest.trades_detail)
        weights = dict(portfolio_weights or {})
        asset_returns = dict(portfolio_returns or {})
        portfolio_context_available = bool(weights or portfolio_returns)
        candidate_id = instrument_uid
        if candidate_id not in asset_returns:
            asset_returns[candidate_id] = self._returns(ordered)
        impact = (
            PortfolioImpactService.calculate(
                weights=weights,
                asset_returns=asset_returns,
                candidate_id=candidate_id,
                candidate_weight=candidate_weight,
                candidate_expected_return_pct=ev.expected_value_pct,
                concentration_penalty_pct=concentration_penalty_pct,
            )
            if portfolio_context_available and (candidate_weight > 0 or weights)
            else self._empty_portfolio()
        )
        portfolio_confidence = self._portfolio_confidence(impact, portfolio_context_available)
        edge_reliability = ev.edge_reliability_pct if ev.available and ev.edge_reliability_pct is not None else 0.0
        strategy_confidence_component = min(evidence_strategy_result.stability, edge_reliability)
        confidence = calculate_confidence(
            strategy_quality=strategy_confidence_component,
            forecast_quality=forecast_quality_score or 0.0,
            regime_confidence=regime_confidence,
            portfolio_confidence=portfolio_confidence,
            observations=ev.observations if ev.available else 0,
            uncertainty_width_pct=ev.uncertainty_width_pct if ev.available else None,
        )
        opportunity = OpportunityEngineV08.evaluate(
            analysis=analysis,
            candles=ordered,
            strategy_result=evidence_strategy_result,
            expected_value=ev,
            portfolio_impact=impact,
            robustness_score=evidence_strategy_result.stability,
            forecast_quality_score=forecast_quality_score,
            confidence_score=confidence.overall_confidence,
        )
        return AnalysisPipelineV08Result(
            analysis, opportunity, ev, impact,
            forecast_quality_score, regime_confidence, evidence_strategy,
            portfolio_context_available, confidence,
        )


__all__ = ["ANALYSIS_PIPELINE_V08_VERSION", "AnalysisPipelineV08Result", "AnalysisPipelineServiceV08"]
