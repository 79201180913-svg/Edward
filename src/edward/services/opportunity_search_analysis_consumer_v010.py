from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.analysis_pipeline_service_v082 import AnalysisPipelineV082Result

CanonicalAnalysisResult: TypeAlias = AnalysisPipelineV08Result | AnalysisPipelineV082Result


@dataclass(frozen=True, slots=True)
class OpportunityAnalysisViewV010:
    """Read-only view of the canonical analysis result consumed by Opportunity Search.

    This adapter deliberately performs no analysis, forecasting, opportunity scoring,
    decision-making, trade planning, or position sizing. It only exposes values that
    have already been calculated by the Analysis Pipeline.
    """

    analysis_result: CanonicalAnalysisResult
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
    def from_result(result: CanonicalAnalysisResult) -> OpportunityAnalysisViewV010:
        if not isinstance(result, (AnalysisPipelineV08Result, AnalysisPipelineV082Result)):
            raise TypeError("Opportunity Search requires AnalysisPipelineV08Result or AnalysisPipelineV082Result")

        base = getattr(result, "base", None)
        confidence = getattr(result, "confidence", None)
        if confidence is None and base is not None:
            confidence = getattr(base, "confidence", None)

        trading_path_research = getattr(result, "trading_path_research", None)
        version = getattr(result, "version", "")

        return OpportunityAnalysisViewV010(
            analysis_result=result,
            analysis=result.analysis,
            opportunity=result.opportunity,
            expected_value=result.expected_value,
            portfolio_impact=result.portfolio_impact,
            forecast_quality_score=getattr(result, "forecast_quality_score", None),
            regime_confidence=getattr(result, "regime_confidence", None),
            evidence_strategy=getattr(result, "evidence_strategy", None),
            portfolio_context_available=bool(getattr(result, "portfolio_context_available", False)),
            confidence=confidence,
            trading_path_research=trading_path_research,
            version=version,
        )


__all__ = ["CanonicalAnalysisResult", "OpportunityAnalysisViewV010", "OpportunityAnalysisConsumerV010"]
