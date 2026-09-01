from __future__ import annotations

import logging
from typing import Any, Sequence

from edward.domain import TradingPathAnalysisV012, TradingPathOpportunity
from edward.services.opportunity_engine_v08 import OpportunityEngineV08

logger = logging.getLogger(__name__)


class TradingPathOpportunityBuilderV012:
    """Build a path-level Opportunity without making a final trade decision.

    The existing OpportunityEngineV08 remains the scoring implementation. This
    adapter prevents the path-centric pipeline from treating a StrategyResult as
    the authoritative unit of analysis. Until path-specific realized trades are
    available, EV and risk are supplied explicitly by the caller.
    """

    @staticmethod
    def from_components(
        analysis: TradingPathAnalysisV012,
        *,
        expected_value_pct: float | None,
        risk_score: float | None,
        risk_gate: bool | None,
        score: float | None = None,
        confidence: float | None = None,
    ) -> TradingPathAnalysisV012:
        opportunity = TradingPathOpportunity(
            score=score,
            confidence=confidence,
            expected_value_pct=expected_value_pct,
            risk_score=risk_score,
            risk_gate=risk_gate,
        )
        logger.warning(
            "[V012 PATH OPPORTUNITY] ticker=%s hypothesis=%s expected_value=%s risk_score=%s risk_gate=%s score=%s confidence=%s",
            analysis.ticker,
            analysis.hypothesis,
            expected_value_pct,
            risk_score,
            risk_gate,
            score,
            confidence,
        )
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
            opportunity=opportunity,
            current_state=analysis.current_state,
            decision=analysis.decision,
            status=analysis.status,
            rank=analysis.rank,
        )

    @staticmethod
    def legacy_score_inputs(
        *,
        analysis: TradingPathAnalysisV012,
        legacy_strategy_result: Any,
        candles: list[Any],
        expected_value: Any,
        portfolio_impact: Any,
        robustness_score: float | None = None,
        forecast_quality_score: float | None = None,
        confidence_score: float | None = None,
    ):
        """Delegate scoring to the existing engine for compatibility migration."""
        return OpportunityEngineV08.score(
            analysis=legacy_strategy_result.analysis if hasattr(legacy_strategy_result, "analysis") else legacy_strategy_result,
            strategy_result=legacy_strategy_result.strategy_result if hasattr(legacy_strategy_result, "strategy_result") else legacy_strategy_result,
            candles=candles,
            expected_value=expected_value,
            portfolio_impact=portfolio_impact,
            robustness_score=robustness_score,
            forecast_quality_score=forecast_quality_score,
            confidence_score=confidence_score,
        )


__all__ = ["TradingPathOpportunityBuilderV012"]
