from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from edward.services.analysis_pipeline_service_v081 import (
    AnalysisPipelineServiceV081,
    AnalysisPipelineV081Result,
)
from edward.services.fundamental_analysis_service_v082 import (
    FundamentalAnalysisResult,
    FundamentalAnalysisServiceV082,
)

ANALYSIS_PIPELINE_V082_VERSION = "0.8.2"


@dataclass(frozen=True, slots=True)
class AnalysisPipelineV082Result:
    """v0.8.2 result: v0.8.1 pipeline plus structured fundamental analysis."""

    base: AnalysisPipelineV081Result
    fundamental: FundamentalAnalysisResult
    version: str = ANALYSIS_PIPELINE_V082_VERSION

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
    def confidence(self):
        return self.base.confidence


class AnalysisPipelineServiceV082:
    """Additive v0.8.2 facade over the stable v0.8.1 analysis pipeline.

    Fundamental analysis is calculated from the same contract-mapped data and
    uses the selected trading profile for fundamental group weighting. It does
    not yet modify the v0.8.1 multifactor score, overlay or execution decision.
    """

    def __init__(self, *, base_pipeline: AnalysisPipelineServiceV081 | None = None) -> None:
        self.base_pipeline = base_pipeline or AnalysisPipelineServiceV081()

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
        **kwargs: Any,
    ) -> AnalysisPipelineV082Result:
        result = self.base_pipeline.analyze(
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
            fundamentals=fundamentals,
            **kwargs,
        )
        fundamental = FundamentalAnalysisServiceV082.analyze(fundamentals, profile=profile)
        return AnalysisPipelineV082Result(base=result, fundamental=fundamental)


__all__ = [
    "ANALYSIS_PIPELINE_V082_VERSION",
    "AnalysisPipelineV082Result",
    "AnalysisPipelineServiceV082",
]
