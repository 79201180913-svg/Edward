from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from edward.services.analysis_pipeline_service_v081 import (
    AnalysisPipelineServiceV081,
    AnalysisPipelineV081Result,
)
from edward.services.fundamental_analysis_service_v082 import (
    FundamentalAnalysisResult,
    FundamentalAnalysisServiceV082,
)
from edward.services.fundamental_factor_adapter_v082 import FundamentalFactorAdapterV082
from edward.services.multifactor_normalization_v081 import normalize
from edward.services.multifactor_overlay_service_v081 import MultiFactorOverlayServiceV081

ANALYSIS_PIPELINE_V082_VERSION = "0.8.2"


@dataclass(frozen=True, slots=True)
class AnalysisPipelineV082Result:
    """v0.8.2 result: v0.8.1 pipeline with the structured fundamental layer wired in."""

    base: Any
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
    """v0.8.2 facade reusing the stable v0.8.1 factor pipeline.

    The structured fundamental result is calculated for every caller. When the
    supplied base result exposes the v0.8.1 multifactor contract, only its
    fundamentals factor is replaced and the existing normalization/overlay is
    re-applied. Lightweight test doubles and compatible alternate base results
    that do not expose multifactor are returned unchanged apart from the added
    structured fundamental result.
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
        base_result = self.base_pipeline.analyze(
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
        if not hasattr(base_result, "multifactor"):
            return AnalysisPipelineV082Result(base=base_result, fundamental=fundamental)

        adapted_fundamental = FundamentalFactorAdapterV082.adapt(fundamental)
        multifactor = replace(base_result.multifactor, fundamentals=adapted_fundamental)
        multifactor = normalize(
            multifactor,
            portfolio_context_available=bool(
                portfolio_weights
                or portfolio_returns
                or candidate_weight > 0
                or kwargs.get("current_weight_pct", 0.0) > 0
                or kwargs.get("marginal_risk_pct", 0.0) != 0
                or kwargs.get("diversification_benefit_pct", 0.0) != 0
            ),
            session_available=kwargs.get("session_name") is not None,
        )
        adjusted, overlay = MultiFactorOverlayServiceV081.apply(base_result.base, multifactor)
        integrated_base = replace(base_result, base=adjusted, multifactor=multifactor, overlay=overlay)
        return AnalysisPipelineV082Result(base=integrated_base, fundamental=fundamental)


__all__ = [
    "ANALYSIS_PIPELINE_V082_VERSION",
    "AnalysisPipelineV082Result",
    "AnalysisPipelineServiceV082",
]
