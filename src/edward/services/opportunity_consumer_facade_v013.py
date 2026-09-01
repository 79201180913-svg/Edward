from __future__ import annotations

from typing import Iterable

from edward.domain import TradingPathAnalysisV012
from edward.services.trading_path_opportunity_consumer_v013 import (
    InstrumentOpportunityV013,
    TradingPathOpportunityConsumerV013,
)


class OpportunityConsumerFacadeV013:
    """Stable Opportunity-facing facade over canonical v0.8.12 path analysis."""

    @staticmethod
    def from_analyses(
        analyses: Iterable[TradingPathAnalysisV012],
    ) -> tuple[InstrumentOpportunityV013, ...]:
        """Project canonical analysis into one opportunity record per instrument."""
        return TradingPathOpportunityConsumerV013.build(analyses)


__all__ = ["OpportunityConsumerFacadeV013"]
