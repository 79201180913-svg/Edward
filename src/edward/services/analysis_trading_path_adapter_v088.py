from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.trading_path_candidate_service_v088 import TradingPathCandidateServiceV088
from edward.services.trading_path_ranking_v088 import RankedTradingPathV088, TradingPathRankingServiceV088

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisTradingPathResearchV088:
    analysis: AnalysisResult
    ranked_candidates: tuple[RankedTradingPathV088, ...]


class AnalysisTradingPathAdapterV088:
    """Add v0.8.8 research candidates to the existing v0.8.7 analysis.

    The wrapped AnalysisServiceV08 remains authoritative for recommendation,
    Quality Gate, Walk-Forward and execution. This adapter only exposes a
    research-side candidate set derived from the already-computed conditional
    discovery result.
    """

    def __init__(self, analysis_service: AnalysisServiceV08 | None = None) -> None:
        self.analysis_service = analysis_service or AnalysisServiceV08()

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
    ) -> AnalysisTradingPathResearchV088:
        ordered = tuple(candles)
        analysis = self.analysis_service.analyze(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=ordered,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
        )
        diagnostics = self.analysis_service.last_diagnostics
        if diagnostics is None or diagnostics.conditional_discovery is None:
            logger.warning("[V088 TRADING PATH ADAPTER] ticker=%s candidates=0 reason=no_conditional_discovery", ticker)
            return AnalysisTradingPathResearchV088(analysis=analysis, ranked_candidates=())

        candidates = TradingPathCandidateServiceV088.promote(
            diagnostics.conditional_discovery,
            instrument_uid=instrument_uid,
            ticker=ticker,
        )
        ranked = TradingPathRankingServiceV088.rank_and_deduplicate(candidates)
        logger.warning(
            "[V088 TRADING PATH RANKING] ticker=%s candidates=%d ranked=%d recommendation_unchanged=%s",
            ticker,
            len(candidates),
            len(ranked),
            analysis.recommendation,
        )
        for rank, item in enumerate(ranked, 1):
            rule = item.candidate.rule
            logger.warning(
                "[V088 TRADING PATH RANKED] ticker=%s rank=%d hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d score=%.6f status=%s",
                ticker,
                rank,
                rule.hypothesis,
                rule.regime,
                rule.volatility_bucket,
                rule.direction,
                rule.horizon,
                item.score,
                item.candidate.status,
            )
        return AnalysisTradingPathResearchV088(analysis=analysis, ranked_candidates=ranked)


__all__ = ["AnalysisTradingPathResearchV088", "AnalysisTradingPathAdapterV088"]
