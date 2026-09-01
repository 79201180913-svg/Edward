from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.trading_path_candidate_service_v088 import TradingPathCandidateServiceV088
from edward.services.trading_path_ranking_v088 import RankedTradingPathV088, TradingPathRankingServiceV088
from edward.services.trading_path_validation_pipeline_v088 import TradingPathPipelineResultV088, TradingPathValidationPipelineV088
from edward.services.economic_validation_v088 import TradingCostModelV088
from edward.services.trading_path_overlap_audit_v088 import TradingPathOverlapAuditV088, TradingPathOverlapEvidenceV088
from edward.services.trading_path_multiple_testing_v088 import TradingPathMultipleTestingEvidenceV088, TradingPathMultipleTestingServiceV088
from edward.services.trading_path_promotion_gate_v088 import TradingPathPromotionGateV088, TradingPathPromotionResultV088
from edward.services.market_context_shadow_scoring_v011 import (
    MarketContextShadowScoreV011,
    MarketContextShadowScoringServiceV011,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisTradingPathResearchV088:
    analysis: AnalysisResult
    ranked_candidates: tuple[RankedTradingPathV088, ...]
    validation_results: tuple[TradingPathPipelineResultV088, ...] = ()
    overlap_evidence: tuple[TradingPathOverlapEvidenceV088, ...] = ()
    multiple_testing_evidence: tuple[TradingPathMultipleTestingEvidenceV088, ...] = ()
    promotion_results: tuple[TradingPathPromotionResultV088, ...] = ()
    market_context_shadow: tuple[tuple[RankedTradingPathV088, MarketContextShadowScoreV011], ...] = ()


class AnalysisTradingPathAdapterV088:
    """Add v0.8.8 research validation plus optional v0.11 shadow context ranking."""

    def __init__(self, analysis_service: AnalysisServiceV08 | None = None) -> None:
        self.analysis_service = analysis_service or AnalysisServiceV08()

    @staticmethod
    def _resolve_market_context(market_context: Any, instrument_uid: str) -> Any:
        if market_context is not None:
            return market_context
        try:
            from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011
            snapshot = MarketContextRuntimeServiceV011.last_built_snapshot
            if snapshot is not None and snapshot.instrument_id == instrument_uid:
                return snapshot
        except Exception:
            logger.debug("[V011 MARKET SHADOW] latest snapshot bridge unavailable", exc_info=True)
        return None

    def _research_from_analysis(
        self,
        *,
        analysis: AnalysisResult,
        instrument_uid: str,
        ticker: str,
        candles: tuple[Candle, ...],
        market_context: Any = None,
    ) -> AnalysisTradingPathResearchV088:
        diagnostics = self.analysis_service.last_diagnostics
        if diagnostics is None or diagnostics.conditional_discovery is None:
            logger.warning("[V088 TRADING PATH ADAPTER] ticker=%s candidates=0 validation=0 reason=no_conditional_discovery", ticker)
            return AnalysisTradingPathResearchV088(analysis=analysis, ranked_candidates=())
        discovery = diagnostics.conditional_discovery
        ranked = TradingPathRankingServiceV088.rank_and_deduplicate(
            TradingPathCandidateServiceV088.promote(discovery, instrument_uid=instrument_uid, ticker=ticker)
        )
        candidates = tuple(item.candidate for item in ranked)
        legacy_cost_model = getattr(self.analysis_service, "costs", None)
        cost_model = TradingCostModelV088.from_legacy(legacy_cost_model) if legacy_cost_model is not None else TradingCostModelV088()
        validation_results = tuple(
            TradingPathValidationPipelineV088.run(item.candidate, candles, discovery.observations, cost_model)
            for item in ranked
        )
        overlap_evidence = tuple(
            TradingPathOverlapAuditV088.audit(item.candidate, candidates, discovery.observations)
            for item in ranked
        )
        multiple_testing_evidence = tuple(
            TradingPathMultipleTestingServiceV088.evaluate(
                mean_return_pct=result.statistical_evidence.mean_return_pct,
                standard_error_pct=result.statistical_evidence.standard_error_pct,
                tests_count=len(ranked),
            )
            for result in validation_results
        )
        promotion_results = tuple(
            TradingPathPromotionGateV088.evaluate(
                result,
                overlap=overlap,
                multiple_testing=multiple_testing,
            )
            for result, overlap, multiple_testing in zip(
                validation_results, overlap_evidence, multiple_testing_evidence
            )
        )

        resolved_context = self._resolve_market_context(market_context, instrument_uid)
        shadow = MarketContextShadowScoringServiceV011.rank(ranked, resolved_context)

        if shadow:
            changed = sum(item.rank_delta != 0 for _, item in shadow)
            mean_abs_delta = sum(abs(item.score_delta) for _, item in shadow) / len(shadow)
            logger.warning(
                "[V011 MARKET SHADOW SUMMARY] ticker=%s benchmark=%s candidates=%d rank_changed=%d mean_abs_score_delta=%.4f",
                ticker,
                getattr(resolved_context, "benchmark_id", "UNKNOWN"),
                len(shadow),
                changed,
                mean_abs_delta,
            )
            for item, score in shadow:
                rule = item.candidate.rule
                logger.warning(
                    "[V011 MARKET SHADOW RANK] ticker=%s baseline_rank=%d context_rank=%d rank_delta=%d hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d baseline_score=%.6f context_score=%.6f delta=%.6f regime_compat=%s rs_component=%.6f vol_component=%.6f confidence_hint_delta=%.6f",
                    ticker,
                    score.baseline_rank,
                    score.context_rank,
                    score.rank_delta,
                    rule.hypothesis,
                    rule.regime,
                    rule.volatility_bucket,
                    rule.direction,
                    rule.horizon,
                    score.baseline_score,
                    score.context_adjusted_score,
                    score.score_delta,
                    score.regime_compatibility,
                    score.relative_strength_component,
                    score.volatility_component,
                    score.confidence_hint_delta,
                )
        else:
            logger.warning(
                "[V011 MARKET SHADOW SUMMARY] ticker=%s status=SKIPPED reason=no_full_market_context",
                ticker,
            )

        ordered_ranked = ranked
        ordered_validation = validation_results
        ordered_overlap = overlap_evidence
        ordered_multiple = multiple_testing_evidence
        ordered_promotion = promotion_results

        if shadow:
            ordered_shadow = tuple(sorted(shadow, key=lambda pair: pair[1].context_rank))
            baseline_index = {id(item): index for index, item in enumerate(ranked)}
            ordered_ranked = tuple(item for item, _ in ordered_shadow)
            index_order = tuple(baseline_index[id(item)] for item in ordered_ranked)
            ordered_validation = tuple(validation_results[index] for index in index_order)
            ordered_overlap = tuple(overlap_evidence[index] for index in index_order)
            ordered_multiple = tuple(multiple_testing_evidence[index] for index in index_order)
            ordered_promotion = tuple(promotion_results[index] for index in index_order)
            logger.warning(
                "[V011 MARKET-AWARE RANKING] ticker=%s benchmark=%s baseline_top=%s context_top=%s changed=%d",
                ticker,
                getattr(resolved_context, "benchmark_id", "UNKNOWN"),
                ranked[0].candidate.rule.hypothesis if ranked else "NONE",
                ordered_ranked[0].candidate.rule.hypothesis if ordered_ranked else "NONE",
                sum(index != position for position, index in enumerate(index_order)),
            )

        logger.warning(
            "[V088 TRADING PATH RANKING] ticker=%s candidates=%d ranked=%d validated=%d overlap_audited=%d promotion_evaluated=%d recommendation_unchanged=%s",
            ticker,
            len(candidates),
            len(ordered_ranked),
            len(ordered_validation),
            len(ordered_overlap),
            len(ordered_promotion),
            analysis.recommendation,
        )
        for rank, item in enumerate(ordered_ranked, 1):
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
        for result, overlap, multiple_testing, promotion in zip(
            ordered_validation, ordered_overlap, ordered_multiple, ordered_promotion
        ):
            evidence = result.statistical_evidence
            logger.warning(
                "[V088 TRADING PATH VALIDATED] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d trades=%d gross=%.6f net=%.6f mean=%.6f ci95=[%.6f,%.6f] adjusted_ci=[%.6f,%.6f] positive_blocks=%d event_overlap=%.6f holding_overlap=%.6f multiple_tests=%d promotion=%s reasons=%s",
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
                multiple_testing.adjusted_ci95_low_pct,
                multiple_testing.adjusted_ci95_high_pct,
                evidence.positive_temporal_blocks,
                overlap.max_event_overlap_ratio,
                overlap.max_holding_overlap_ratio,
                multiple_testing.tests_count,
                promotion.status.value,
                ",".join(promotion.reasons) or "NONE",
            )

        return AnalysisTradingPathResearchV088(
            analysis=analysis,
            ranked_candidates=ordered_ranked,
            validation_results=ordered_validation,
            overlap_evidence=ordered_overlap,
            multiple_testing_evidence=ordered_multiple,
            promotion_results=ordered_promotion,
            market_context_shadow=shadow,
        )

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
        market_context: Any = None,
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
        return self.research_from_analysis(
            analysis=analysis,
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=ordered,
            market_context=market_context,
        )

    def research_from_analysis(
        self,
        *,
        analysis: AnalysisResult,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        market_context: Any = None,
    ) -> AnalysisTradingPathResearchV088:
        return self._research_from_analysis(
            analysis=analysis,
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=tuple(candles),
            market_context=market_context,
        )


__all__ = ["AnalysisTradingPathResearchV088", "AnalysisTradingPathAdapterV088"]
