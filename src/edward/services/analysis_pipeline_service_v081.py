from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08, AnalysisPipelineV08Result
from edward.services.multifactor_analysis_service_v081 import MultiFactorAnalysisServiceV081, MultiFactorResult
from edward.services.multifactor_normalization_v081 import normalize
from edward.services.multifactor_overlay_service_v081 import MultiFactorOverlayResult, MultiFactorOverlayServiceV081

ANALYSIS_PIPELINE_V081_VERSION = "0.8.1"


@dataclass(frozen=True, slots=True)
class AnalysisPipelineV081Result:
    base: AnalysisPipelineV08Result
    multifactor: MultiFactorResult
    overlay: MultiFactorOverlayResult
    version: str = ANALYSIS_PIPELINE_V081_VERSION

    @property
    def analysis(self):
        return self.base.analysis

    @property
    def opportunity(self):
        return self.base.opportunity

    @property
    def expected_value(self):
        return self.base.expected_value

    @property
    def portfolio_impact(self):
        return self.base.portfolio_impact

    @property
    def forecast_quality_score(self):
        return self.base.forecast_quality_score

    @property
    def regime_confidence(self):
        return self.base.regime_confidence

    @property
    def evidence_strategy(self):
        return self.base.evidence_strategy

    @property
    def portfolio_context_available(self):
        return self.base.portfolio_context_available

    @property
    def confidence(self):
        base_confidence = self.base.confidence
        if base_confidence is None:
            return None
        level = "High" if self.overlay.adjusted_confidence >= 75.0 else "Medium" if self.overlay.adjusted_confidence >= 55.0 else "Low"
        return replace(
            base_confidence,
            overall_confidence=self.overlay.adjusted_confidence,
            level=level,
        )


class AnalysisPipelineServiceV081:
    """v0.8.1 additive facade over the stable v0.8 analysis pipeline."""

    def __init__(self, *, base_pipeline: AnalysisPipelineServiceV08 | None = None) -> None:
        self.base_pipeline = base_pipeline or AnalysisPipelineServiceV08()

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles,
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
        portfolio_weights: Mapping[str, float] | None = None,
        portfolio_returns: Mapping[str, Sequence[float]] | None = None,
        candidate_weight: float = 0.0,
        concentration_penalty_pct: float = 0.0,
        fundamentals: Any = None,
        order_book: Any = None,
        trades: Sequence[Any] | None = None,
        current_signal: Any = None,
        historical_signals: Sequence[Any] | None = None,
        event: Any = None,
        historical_gaps_pct: Sequence[float] | None = None,
        historical_event_vol_pct: Sequence[float] | None = None,
        dividend_data: Any = None,
        insider_transactions: Sequence[Any] | None = None,
        session_name: str | None = None,
        session_execution_allowed: bool = True,
        risk_data: Any = None,
        current_weight_pct: float = 0.0,
        marginal_risk_pct: float = 0.0,
        diversification_benefit_pct: float = 0.0,
        expected_return_impact_pct: float = 0.0,
        max_position_weight_pct: float | None = None,
        current_price: float | None = None,
    ) -> AnalysisPipelineV081Result:
        base = self.base_pipeline.analyze(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=candles,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
            portfolio_weights=portfolio_weights,
            portfolio_returns=portfolio_returns,
            candidate_weight=candidate_weight,
            concentration_penalty_pct=concentration_penalty_pct,
        )
        multifactor = MultiFactorAnalysisServiceV081.analyze(
            fundamentals=fundamentals,
            order_book=order_book,
            trades=trades,
            candles=candles,
            current_signal=current_signal,
            historical_signals=historical_signals,
            event=event,
            historical_gaps_pct=historical_gaps_pct,
            historical_event_vol_pct=historical_event_vol_pct,
            dividend_data=dividend_data,
            insider_transactions=insider_transactions,
            session_name=session_name,
            session_execution_allowed=session_execution_allowed,
            risk_data=risk_data,
            current_weight_pct=current_weight_pct,
            marginal_risk_pct=marginal_risk_pct,
            diversification_benefit_pct=diversification_benefit_pct,
            expected_return_impact_pct=expected_return_impact_pct,
            max_position_weight_pct=max_position_weight_pct,
            current_price=current_price,
        )
        multifactor = normalize(
            multifactor,
            portfolio_context_available=bool(
                portfolio_weights or portfolio_returns or candidate_weight > 0 or current_weight_pct > 0 or marginal_risk_pct != 0 or diversification_benefit_pct != 0
            ),
            session_available=session_name is not None,
        )
        adjusted, overlay = MultiFactorOverlayServiceV081.apply(base, multifactor)
        return AnalysisPipelineV081Result(adjusted, multifactor, overlay)


__all__ = ["ANALYSIS_PIPELINE_V081_VERSION", "AnalysisPipelineV081Result", "AnalysisPipelineServiceV081"]
