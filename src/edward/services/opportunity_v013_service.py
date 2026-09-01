from __future__ import annotations

from typing import Iterable

from edward.domain import TradingPathAnalysisV012
from edward.services.opportunity_consumer_facade_v013 import OpportunityConsumerFacadeV013
from edward.services.trading_path_opportunity_runtime_service_v013 import TradingPathOpportunityRuntimeServiceV013


class OpportunityV013Service:
    """Production entry point for opportunities backed by canonical Trading Paths."""

    def __init__(self, runtime: TradingPathOpportunityRuntimeServiceV013 | None = None) -> None:
        self.runtime = runtime or TradingPathOpportunityRuntimeServiceV013()

    def from_analyses(self, analyses: Iterable[TradingPathAnalysisV012]):
        return OpportunityConsumerFacadeV013.from_analyses(analyses)

    def scan_instrument(self, *, instrument_uid: str, ticker: str, candles: Iterable[object], profile: str = "medium_term", risk_profile: str = "balanced"):
        return self.runtime.scan_instrument(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=candles,
            profile=profile,
            risk_profile=risk_profile,
        )


__all__ = ["OpportunityV013Service"]
