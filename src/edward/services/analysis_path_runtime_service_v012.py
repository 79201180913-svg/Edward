from __future__ import annotations

import logging
from typing import Iterable

from edward.domain import TradingPathAnalysisV012
from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012

logger = logging.getLogger(__name__)


class AnalysisPathRuntimeServiceV012:
    """Runtime bridge for the v0.8.12 path-centric analysis output.

    The legacy AnalysisServiceV08 remains untouched for backward compatibility.
    This bridge executes the same discovery source and exposes the canonical path
    analysis as a first-class runtime result.
    """

    def __init__(self, analysis_service: AnalysisServiceV08 | None = None) -> None:
        self.analysis_service = analysis_service or AnalysisServiceV08()

    def analyze_paths(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
    ) -> tuple[TradingPathAnalysisV012, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086
        from edward.services.trading_path_candidate_service_v088 import TradingPathCandidateServiceV088

        discovery = ConditionalDiscoveryServiceV086.run(ordered)
        candidates = TradingPathCandidateServiceV088.promote(
            discovery,
            instrument_uid=instrument_uid,
            ticker=ticker,
        )
        result = TradingPathAnalysisBuilderV012.build(candidates, ordered)
        logger.warning(
            "[V012 PATH RUNTIME] ticker=%s candidates=%d analyses=%d validated=%d rejected=%d",
            ticker,
            len(candidates),
            len(result),
            sum(item.status.value == "validated" for item in result),
            sum(item.status.value == "rejected" for item in result),
        )
        return result


__all__ = ["AnalysisPathRuntimeServiceV012"]
