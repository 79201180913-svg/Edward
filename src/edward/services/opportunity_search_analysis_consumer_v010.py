from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result


@dataclass(frozen=True, slots=True)
class OpportunityAnalysisViewV010:
    """Read-only view of the canonical analysis result consumed by Opportunity Search.

    This adapter deliberately performs no analysis, forecasting, opportunity scoring,
    decision-making, trade planning, or position sizing. It only exposes values that
    have already been calculated by AnalysisPipelineServiceV08.
    """

    analysis_result: AnalysisPipelineV08Result
    analysis: Any
    opportunity: Any
    expected_value: Any
    portfolio_impact: Any
    forecast_quality_score: float | None
    regime_confidence: float | None
    evidence_strategy: str | None
    portfolio_context_available: bool
    confidence: Any
    trading_path_research: Any
    version: str


class OpportunityAnalysisConsumerV010:
    """Consume, without recalculating, a canonical v0.8 analysis result."""

    @staticmethod
    def from_result(result: AnalysisPipelineV08Result) -> OpportunityAnalysisViewV010:
        if not isinstance(result, AnalysisPipelineV08Result):
            raise TypeError("Opportunity Search requires AnalysisPipelineV08Result")

        return OpportunityAnalysisViewV010(
            analysis_result=result,
            analysis=result.analysis,
            opportunity=result.opportunity,
            expected_value=result.expected_value,
            portfolio_impact=result.portfolio_impact,
            forecast_quality_score=result.forecast_quality_score,
            regime_confidence=result.regime_confidence,
            evidence_strategy=result.evidence_strategy,
            portfolio_context_available=result.portfolio_context_available,
            confidence=result.confidence,
            trading_path_research=result.trading_path_research,
            version=result.version,
        )


__all__ = ["OpportunityAnalysisViewV010", "OpportunityAnalysisConsumerV010"]
