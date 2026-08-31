from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.trading_path_candidate_service_v088 import TradingPathCandidateServiceV088
from edward.services.trading_path_ranking_v088 import RankedTradingPathV088, TradingPathRankingServiceV088
from edward.services.trading_path_validation_pipeline_v088 import TradingPathPipelineResultV088, TradingPathValidationPipelineV088
from edward.services.economic_validation_v088 import TradingCostModelV088

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisTradingPathResearchV088:
    analysis: AnalysisResult
    ranked_candidates: tuple[RankedTradingPathV088, ...]
    validation_results: tuple[TradingPathPipelineResultV088, ...] = ()


class AnalysisTradingPathAdapterV088:
    """Add v0.8.8 research validation to the existing v0.8.7 analysis.

    The wrapped AnalysisServiceV08 remains authoritative for recommendation,
    Quality Gate, Walk-Forward and execution. The adapter reuses the canonical
    observations already produced by ConditionalDiscoveryServiceV086 and runs
    the v0.8.8 validation pipeline strictly as research diagnostics.
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
            logger.warning("[V088 TRADING PATH ADAPTER] ticker=%s candidates=0 validation=0 reason=no_conditional_discovery", ticker)
            return AnalysisTradingPathResearchV088(analysis=analysis, ranked_candidates=())

        discovery = diagnostics.conditional_discovery
        candidates = TradingPathCandidateServiceV088.promote(
            discovery,
            instrument_uid=instrument_uid,
            ticker=ticker,
        )
        ranked = TradingPathRankingServiceV088.rank_and_deduplicate(candidates)
        observations = discovery.observations
        validation_results: list[TradingPathPipelineResultV088] = []
        cost_model = getattr(self.analysis_service, "costs", None) or TradingCostModelV088()
        for item in ranked:
            result = TradingPathValidationPipelineV088.run(
                item.candidate,
                ordered,
                observations,
                cost_model,
            )
            validation_results.append(result)
        logger.warning(
            "[V088 TRADING PATH RANKING] ticker=%s candidates=%d ranked=%d validated=%d recommendation_unchanged=%s",
            ticker,
            len(candidates),
            len(ranked),
            len(validation_results),
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
        for result in validation_results:
            evidence = result.statistical_evidence
            logger.warning(
                "[V088 TRADING PATH VALIDATED] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d trades=%d gross=%.6f net=%.6f mean=%.6f ci95=[%.6f,%.6f] positive_blocks=%d",
                ticker,
                result.candidate.rule.hypothesis,
                result.candidate.rule.regime,
                result.candidate.rule.volatility_bucket,
                result.candidate.rule.direction,
                result.candidate.rule.horizon,
                result.trades,
                result.gross_return_pct,
                result.net_return_pct,
                evidence.mean_return_pct,
                evidence.ci95_low_pct,
                evidence.ci95_high_pct,
                evidence.positive_temporal_blocks,
            )
        return AnalysisTradingPathResearchV088(
            analysis=analysis,
            ranked_candidates=ranked,
            validation_results=tuple(validation_results),
        )


__all__ = ["AnalysisTradingPathResearchV088", "AnalysisTradingPathAdapterV088"]
