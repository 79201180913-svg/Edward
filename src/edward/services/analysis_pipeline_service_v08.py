from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.expected_value_engine_v08 import ExpectedValueEngine, ExpectedValueResult
from edward.services.forecast_quality_adapter_v08 import ForecastQualityAdapterV08
from edward.services.opportunity_engine import OpportunityResult
from edward.services.opportunity_engine_v08 import OpportunityEngineV08
from edward.services.portfolio_impact_service_v08 import PortfolioImpactResult, PortfolioImpactService
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
    version: str = ANALYSIS_PIPELINE_V08_VERSION


class AnalysisPipelineServiceV08:
    """Compose v0.8 analytics while preserving the legacy downstream result contract."""

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
        regime_result = RegimeEngine.classify(ordered)

        forecast_quality_score: float | None = None
        try:
            quality = self.forecast_quality.evaluate(candles=ordered, horizons=(1, 5, 20))
            forecast_quality_score = quality.overall_quality_score
        except ValueError:
            forecast_quality_score = None

        if evidence_strategy_result is None:
            ev = ExpectedValueEngine.from_returns(())
            impact = self._empty_portfolio()
            opportunity = OpportunityEngineV08.evaluate(
                analysis=analysis,
                candles=ordered,
                strategy_result=None,
                expected_value=ev,
                portfolio_impact=impact,
            )
            return AnalysisPipelineV08Result(
                analysis, opportunity, ev, impact,
                forecast_quality_score, regime_result.confidence, None, False,
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
        opportunity = OpportunityEngineV08.evaluate(
            analysis=analysis,
            candles=ordered,
            strategy_result=evidence_strategy_result,
            expected_value=ev,
            portfolio_impact=impact,
            robustness_score=evidence_strategy_result.stability,
            forecast_quality_score=forecast_quality_score,
            confidence_score=min(
                evidence_strategy_result.stability,
                forecast_quality_score if forecast_quality_score is not None else evidence_strategy_result.stability,
                regime_result.confidence,
            ),
        )
        return AnalysisPipelineV08Result(
            analysis, opportunity, ev, impact,
            forecast_quality_score, regime_result.confidence, evidence_strategy,
            portfolio_context_available,
        )


__all__ = ["ANALYSIS_PIPELINE_V08_VERSION", "AnalysisPipelineV08Result", "AnalysisPipelineServiceV08"]
