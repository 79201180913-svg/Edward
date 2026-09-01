from __future__ import annotations

from typing import Iterable

from edward.domain import TradingPathAnalysisV012
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.trading_path_opportunity_consumer_v013 import (
    InstrumentOpportunityV013,
    TradingPathOpportunityConsumerV013,
)


class TradingPathOpportunityRuntimeServiceV013:
    """Canonical v0.8.13 opportunity runtime backed only by Trading Path analysis."""

    def __init__(self, analysis_runtime: AnalysisPathRuntimeServiceV012 | None = None) -> None:
        self.analysis_runtime = analysis_runtime or AnalysisPathRuntimeServiceV012()

    def scan_instrument(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[object],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
    ) -> InstrumentOpportunityV013 | None:
        analyses = self.analysis_runtime.analyze_paths(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=candles,
            profile=profile,
            risk_profile=risk_profile,
        )
        opportunities = TradingPathOpportunityConsumerV013.build(analyses)
        return opportunities[0] if opportunities else None

    def scan_analyses(self, analyses: Iterable[TradingPathAnalysisV012]) -> tuple[InstrumentOpportunityV013, ...]:
        return TradingPathOpportunityConsumerV013.build(analyses)


__all__ = ["TradingPathOpportunityRuntimeServiceV013"]
