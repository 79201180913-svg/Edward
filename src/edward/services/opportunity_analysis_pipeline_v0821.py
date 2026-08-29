from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from edward.api.tinvest_multifactor_client_patch_v081 import install as install_client_patch
from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08
from edward.services.analysis_pipeline_service_v081 import AnalysisPipelineServiceV081
from edward.services.analysis_pipeline_service_v082 import AnalysisPipelineServiceV082
from edward.services.cached_analysis_service_v08 import CachedAnalysisServiceV08
from edward.services.news_intelligence_service_v081 import NewsIntelligenceServiceV081
from edward.services.news_overlay_service_v081 import NewsOverlayServiceV081
from edward.services.opportunity_engine import OpportunityEngine as LegacyOpportunityEngine
from edward.services.semantic_robust_contract_analysis_data_service_v081 import (
    SemanticRobustContractAnalysisDataServiceV081,
)

OPPORTUNITY_ANALYSIS_V0821_VERSION = "0.8.2.1"


@dataclass(frozen=True, slots=True)
class OpportunityAnalysisViewV0821:
    """Legacy-shaped view backed by the canonical v0.8.2 pipeline result."""

    pipeline_result: Any
    strategies: tuple[Any, ...]

    @property
    def market_regime(self):
        return self.pipeline_result.analysis.market_regime

    @property
    def confidence(self):
        return self.pipeline_result.confidence.overall_confidence if self.pipeline_result.confidence is not None else None

    @property
    def opportunity(self):
        return self.pipeline_result.opportunity


class UnifiedOpportunityEngineV0821:
    """Bridge the legacy opportunity-search call site to v0.8.2 opportunity."""

    @staticmethod
    def evaluate(analysis, candles, strategy_result, **kwargs):
        pipeline_result = getattr(analysis, "pipeline_result", None)
        if pipeline_result is not None:
            return pipeline_result.opportunity
        return LegacyOpportunityEngine.evaluate(analysis, candles, strategy_result, **kwargs)


class OpportunityAnalysisPipelineV0821:
    """Provide opportunity search with the canonical v0.8.2 analysis pipeline.

    The adapter deliberately reuses the same contract-data collection and
    news overlay path as the v0.8.2 single-instrument analysis UI. Portfolio
    and position context remains outside this adapter and is applied by the
    opportunity/decision layer.
    """

    def __init__(
        self,
        client: Any,
        *,
        pipeline: AnalysisPipelineServiceV082 | None = None,
        collector: SemanticRobustContractAnalysisDataServiceV081 | None = None,
        cache_store: Any = None,
        force_recompute: bool = False,
    ) -> None:
        install_client_patch()
        self.client = client
        if pipeline is not None:
            self.pipeline = pipeline
            self.cached_analysis = None
        elif cache_store is not None:
            cached_v08 = CachedAnalysisServiceV08(cache_store, force_recompute=force_recompute)
            base_v08 = AnalysisPipelineServiceV08(analysis_service=cached_v08)
            base_v081 = AnalysisPipelineServiceV081(base_pipeline=base_v08)
            self.pipeline = AnalysisPipelineServiceV082(base_pipeline=base_v081)
            self.cached_analysis = cached_v08
        else:
            self.pipeline = AnalysisPipelineServiceV082()
            self.cached_analysis = None
        self.collector = collector or SemanticRobustContractAnalysisDataServiceV081(client)

    @property
    def cache_info(self) -> dict[str, int]:
        if self.cached_analysis is None:
            return {"hits": 0, "misses": 0, "total": 0}
        return self.cached_analysis.cache_info()

    def force_recompute(self) -> None:
        if self.cached_analysis is not None:
            self.cached_analysis.force_recompute = True

    @staticmethod
    def _fundamental_input(fundamentals: Any, instrument: Mapping[str, Any] | None) -> Any:
        """Attach the same instrument semantic context used by the analysis UI."""
        if not isinstance(fundamentals, Mapping):
            return fundamentals
        snapshot = dict(fundamentals)
        context_value = snapshot.get("__instrument_context", {})
        context = dict(context_value) if isinstance(context_value, Mapping) else {}
        instrument = instrument or {}
        for source_key, context_key in (
            ("instrument_type", "instrument_type"),
            ("instrument_kind", "instrument_kind"),
            ("name", "name"),
            ("ticker", "ticker"),
            ("sector", "sector"),
            ("sector_name", "sector_name"),
            ("industry", "industry"),
            ("industry_name", "industry_name"),
            ("asset_class", "asset_class"),
        ):
            value = instrument.get(source_key)
            if value not in (None, ""):
                context[context_key] = value
        if context:
            snapshot["__instrument_context"] = context
        return snapshot

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles,
        profile: str = "medium_term",
        instrument: Mapping[str, Any] | None = None,
        portfolio_weights: Mapping[str, float] | None = None,
        portfolio_returns: Mapping[str, list[float]] | None = None,
        candidate_weight: float = 0.0,
        concentration_penalty_pct: float = 0.0,
    ) -> OpportunityAnalysisViewV0821:
        data = self.collector.collect(str(instrument_uid))
        reports = list(data.reports)
        event = reports[0] if reports else None
        current_signal = data.signals[0] if data.signals else None
        fundamental_input = self._fundamental_input(data.fundamentals, instrument)

        result = self.pipeline.analyze(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=candles,
            profile=profile,
            portfolio_weights=portfolio_weights,
            portfolio_returns=portfolio_returns,
            candidate_weight=candidate_weight,
            concentration_penalty_pct=concentration_penalty_pct,
            fundamentals=fundamental_input,
            order_book=data.order_book,
            trades=data.trades,
            current_signal=current_signal,
            historical_signals=data.signals,
            event=event,
            dividend_data=data.dividends,
            insider_transactions=data.insider_transactions,
            risk_data=data.risk_data,
            instrument_risk_metadata=data.instrument_risk_metadata,
            session_name=data.session_name,
        )

        news_result = NewsIntelligenceServiceV081.analyze(
            data.news,
            instrument_uid=str(instrument_uid),
        )
        adjusted_base, _news_overlay = NewsOverlayServiceV081.apply(result.base.base, news_result)
        result = replace(
            result,
            base=replace(result.base, base=adjusted_base),
        )

        evidence_strategy = None
        for strategy in getattr(result.analysis, "strategies", ()):
            if strategy.strategy == result.evidence_strategy:
                evidence_strategy = strategy
                break
        if evidence_strategy is None and getattr(result.analysis, "strategies", ()):
            evidence_strategy = max(result.analysis.strategies, key=lambda item: item.score)
        strategies = (evidence_strategy,) if evidence_strategy is not None else ()
        return OpportunityAnalysisViewV0821(
            pipeline_result=result,
            strategies=strategies,
        )


__all__ = [
    "OPPORTUNITY_ANALYSIS_V0821_VERSION",
    "OpportunityAnalysisPipelineV0821",
    "OpportunityAnalysisViewV0821",
    "UnifiedOpportunityEngineV0821",
]
