from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping, Sequence

from edward.services.analysis_pipeline_service_v082 import AnalysisPipelineServiceV082
from edward.services.market_benchmark_resolver_v011 import MarketBenchmarkResolverV011
from edward.services.market_context_shadow_scoring_v011 import MarketContextShadowScoringServiceV011
from edward.services.market_data_loader_v011 import MarketDataLoaderV011, MarketDataRequest
from edward.services.market_regime_context_v011 import MarketRegimeContextBuilderV011


ANALYSIS_PIPELINE_V011_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class AnalysisPipelineV011Result:
    """v0.11 result: canonical v0.8.2 analysis plus point-in-time market context."""

    base: Any
    benchmark: Any
    market_context: Any
    version: str = ANALYSIS_PIPELINE_V011_VERSION

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
    def multifactor(self):
        return self.base.multifactor

    @property
    def overlay(self):
        return self.base.overlay

    @property
    def trading_path_research(self):
        """Expose the v0.11 market-aware Trading Path research result."""
        return getattr(getattr(getattr(self.base, "base", None), "base", None), "trading_path_research", None)


class AnalysisPipelineServiceV011:
    """Integrate market context into Trading Path ranking while preserving QG.

    Market context is computed from the instrument's benchmark and then applied
    to the canonical v0.8.8 Trading Path research ranking. The underlying
    statistical validation and Quality Gate remain unchanged; only research
    priority is market-aware in v0.11.0.
    """

    def __init__(
        self,
        *,
        base_pipeline: AnalysisPipelineServiceV082 | None = None,
        benchmark_resolver: type[MarketBenchmarkResolverV011] = MarketBenchmarkResolverV011,
        market_context_builder: MarketRegimeContextBuilderV011 | None = None,
    ) -> None:
        self.base_pipeline = base_pipeline or AnalysisPipelineServiceV082()
        self.benchmark_resolver = benchmark_resolver
        self.market_context_builder = market_context_builder or MarketRegimeContextBuilderV011()

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
        instrument_metadata: Any = None,
        market_candles: Sequence[Any] | None = None,
        market_as_of: datetime | None = None,
        **kwargs: Any,
    ) -> AnalysisPipelineV011Result:
        benchmark = self.benchmark_resolver.resolve(instrument_metadata or {})
        if not benchmark.supported:
            raise ValueError(f"Market context is unsupported: {benchmark.reason}")
        if market_candles is None:
            raise ValueError("market_candles are required when market context is enabled")

        as_of = market_as_of or max(candle.timestamp for candle in candles)
        market_context = self.market_context_builder.build(
            instrument_id=benchmark.benchmark_id or "",
            as_of=as_of,
            candles=market_candles,
        )

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

        market_aware_result = base_result
        v081_result = getattr(base_result, "base", None)
        v08_result = getattr(v081_result, "base", None)
        existing_research = getattr(v08_result, "trading_path_research", None)
        ranked_candidates = getattr(existing_research, "ranked_candidates", ()) if existing_research is not None else ()
        if ranked_candidates:
            shadow = MarketContextShadowScoringServiceV011.rank(ranked_candidates, market_context)
            if shadow:
                market_aware_ranked = tuple(item for item, _ in sorted(shadow, key=lambda pair: pair[1].context_rank))
                market_aware_research = replace(
                    existing_research,
                    ranked_candidates=market_aware_ranked,
                    market_context_shadow=shadow,
                )
                market_aware_v08 = replace(v08_result, trading_path_research=market_aware_research)
                market_aware_v081 = replace(v081_result, base=market_aware_v08)
                market_aware_result = replace(base_result, base=market_aware_v081)
                top = min(shadow, key=lambda pair: pair[1].context_rank)[1]
                logger.warning(
                    "[V011 MARKET-AWARE RANKING] ticker=%s benchmark=%s baseline_top=%d context_top=%d rank_changed=%d",
                    ticker,
                    getattr(market_context, "benchmark_id", "UNKNOWN"),
                    top.baseline_rank,
                    top.context_rank,
                    sum(item.rank_delta != 0 for _, item in shadow),
                )
        else:
            logger.warning("[V011 MARKET-AWARE RANKING] ticker=%s status=SKIPPED reason=no_trading_path_candidates", ticker)

        return AnalysisPipelineV011Result(
            base=market_aware_result,
            benchmark=benchmark,
            market_context=market_context,
        )


__all__ = [
    "ANALYSIS_PIPELINE_V011_VERSION",
    "AnalysisPipelineV011Result",
    "AnalysisPipelineServiceV011",
]
