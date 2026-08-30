from __future__ import annotations

import logging
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
logger = logging.getLogger(__name__)


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
    """Compose v0.8 analytics while preserving the legacy downstream result contract."""

    def __init__(self, *, analysis_service: AnalysisServiceV08 | None = None) -> None:
        self.analysis_service = analysis_service or AnalysisServiceV08()
        self.forecast_quality = ForecastQualityAdapterV08()
        logger.warning(
            "[V083 EXEC] INIT AnalysisPipelineServiceV08 file=%s analysis_service=%s version=%s",
            __file__, type(self.analysis_service).__name__, ANALYSIS_PIPELINE_V08_VERSION,
        )

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
        return max(0.0, min(100.0, 70.0 + impact.diversification_benefit_pct * 5.0 - max(0.0, impact.marginal_risk_pct) * 5.0))

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
        logger.warning(
            "[V083 EXEC] ENTER AnalysisPipelineServiceV08 file=%s ticker=%s instrument_uid=%s profile=%s candles=%d risk_profile=%s horizon=%s",
            __file__, ticker, instrument_uid, profile, len(ordered), risk_profile, horizon,
        )
        analysis = self.analysis_service.analyze(
            instrument_uid=instrument_uid, ticker=ticker, candles=ordered,
            profile=profile, risk_profile=risk_profile, horizon=horizon,
        )
        logger.warning(
            "[V083 EXEC] EXIT AnalysisServiceV08 ticker=%s strategies=%d recommendation=%s score=%.4f",
            ticker, len(analysis.strategies), analysis.recommendation, analysis.score,
        )

        diagnostic_result = max(analysis.strategies, key=lambda item: item.score) if analysis.strategies else None
        diagnostic_strategy = diagnostic_result.strategy if diagnostic_result else None
        backtestable_results = [
            item for item in analysis.strategies
            if bool(item.parameters) and item.wf_windows > 0
        ]
        backtestable_result = max(backtestable_results, key=lambda item: item.score) if backtestable_results else None
        evidence_strategy = diagnostic_strategy
        logger.warning(
            "[V084 EVIDENCE SELECTION] ticker=%s diagnostic_strategy=%s diagnostic_qg=%s diagnostic_wf_windows=%s "
            "diagnostic_parameters=%s backtestable_strategy=%s backtestable_count=%d",
            ticker, diagnostic_strategy,
            diagnostic_result.quality_gate if diagnostic_result else None,
            diagnostic_result.wf_windows if diagnostic_result else None,
            diagnostic_result.parameters if diagnostic_result else None,
            backtestable_result.strategy if backtestable_result else None,
            len(backtestable_results),
        )

        raw_regime = RegimeEngine.classify(ordered)
        regime_confidence = cap_regime_confidence(raw_regime.confidence)
        forecast_quality_score = None
        try:
            forecast_quality_score = self.forecast_quality.evaluate(candles=ordered, horizons=(1, 5, 20)).overall_quality_score
        except ValueError:
            pass

        if diagnostic_result is None:
            ev = ExpectedValueEngine.from_returns(())
            impact = self._empty_portfolio()
            confidence = calculate_confidence(
                strategy_quality=0.0, forecast_quality=forecast_quality_score or 0.0,
                regime_confidence=regime_confidence, portfolio_confidence=0.0, observations=0,
            )
            opportunity = OpportunityEngineV08.evaluate(
                analysis=analysis, candles=ordered, strategy_result=None,
                expected_value=ev, portfolio_impact=impact,
                confidence_score=confidence.overall_confidence,
            )
            logger.warning("[V084 EVIDENCE EMPTY] ticker=%s reason=no_strategy_results", ticker)
            return AnalysisPipelineV08Result(analysis, opportunity, ev, impact, forecast_quality_score, regime_confidence, None, False, confidence)

        if backtestable_result is None:
            logger.warning(
                "[V084 EVIDENCE FALLBACK] ticker=%s diagnostic_strategy=%s action=from_price_returns reason=no_backtestable_strategy",
                ticker, diagnostic_strategy,
            )
            ev = ExpectedValueEngine.from_returns(self._returns(ordered))
            strategy_quality_component = 0.0
        else:
            parameters = dict(backtestable_result.parameters)
            backtest = ResearchBacktestService.run_simple_strategy(
                candles=ordered, strategy=backtestable_result.strategy,
                parameters=parameters, costs=self.analysis_service.costs,
            )
            logger.warning(
                "[V084 EVIDENCE BACKTEST] ticker=%s strategy=%s parameters=%s trades=%d return=%.6f",
                ticker, backtestable_result.strategy, parameters, len(backtest.trades_detail), backtest.net_return_pct,
            )
            ev = ExpectedValueEngine.from_trades(backtest.trades_detail)
            strategy_quality_component = min(
                backtestable_result.stability,
                ev.edge_reliability_pct if ev.available and ev.edge_reliability_pct is not None else 0.0,
            )

        weights = dict(portfolio_weights or {})
        asset_returns = dict(portfolio_returns or {})
        portfolio_context_available = bool(weights or portfolio_returns)
        candidate_id = instrument_uid
        if candidate_id not in asset_returns:
            asset_returns[candidate_id] = self._returns(ordered)
        impact = (
            PortfolioImpactService.calculate(
                weights=weights, asset_returns=asset_returns, candidate_id=candidate_id,
                candidate_weight=candidate_weight, candidate_expected_return_pct=ev.expected_value_pct,
                concentration_penalty_pct=concentration_penalty_pct,
            )
            if portfolio_context_available and (candidate_weight > 0 or weights)
            else self._empty_portfolio()
        )
        portfolio_confidence = self._portfolio_confidence(impact, portfolio_context_available)
        confidence = calculate_confidence(
            strategy_quality=strategy_quality_component,
            forecast_quality=forecast_quality_score or 0.0,
            regime_confidence=regime_confidence,
            portfolio_confidence=portfolio_confidence,
            observations=ev.observations if ev.available else 0,
            uncertainty_width_pct=ev.uncertainty_width_pct if ev.available else None,
        )
        opportunity = OpportunityEngineV08.evaluate(
            analysis=analysis, candles=ordered,
            strategy_result=backtestable_result,
            expected_value=ev, portfolio_impact=impact,
            robustness_score=backtestable_result.stability if backtestable_result else 0.0,
            forecast_quality_score=forecast_quality_score,
            confidence_score=confidence.overall_confidence,
        )
        return AnalysisPipelineV08Result(
            analysis, opportunity, ev, impact, forecast_quality_score,
            regime_confidence, evidence_strategy, portfolio_context_available, confidence,
        )


__all__ = ["ANALYSIS_PIPELINE_V08_VERSION", "AnalysisPipelineV08Result", "AnalysisPipelineServiceV08"]
