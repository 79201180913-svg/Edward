from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace
from typing import Sequence

from edward.domain import TradingPathAnalysisV012, TradingPathMarketContext
from edward.services.market_context_shadow_scoring_v011 import MarketContextShadowScoringServiceV011

logger = logging.getLogger(__name__)


class TradingPathMarketContextServiceV012:
    """Apply the existing v0.11 shadow Market Context scorer to v0.8.12 paths.

    The baseline is the existing path rank encoded on a 0..100 research scale;
    no new evidence or production decision score is introduced. Context remains
    shadow-only and never changes validation or decision fields.
    """

    @staticmethod
    def _baseline_score(rank: int, count: int) -> float:
        if count <= 0:
            return 0.0
        return round(100.0 * (count - rank + 1) / count, 6)

    @classmethod
    def apply(
        cls,
        paths: Sequence[TradingPathAnalysisV012],
        candidates: Sequence[object],
        snapshot: object | None,
    ) -> tuple[TradingPathAnalysisV012, ...]:
        if not paths or snapshot is None or getattr(snapshot, "context_status", "UNAVAILABLE") != "FULL":
            return tuple(paths)

        candidate_by_key = {
            (
                item.rule.instrument_uid,
                item.rule.ticker,
                item.rule.hypothesis,
                item.rule.regime,
                item.rule.volatility_bucket,
                item.rule.direction,
                item.rule.horizon,
            ): item
            for item in candidates
        }
        count = len(paths)
        ranked_items = []
        for path in paths:
            key = (
                path.instrument_uid,
                path.ticker,
                path.hypothesis,
                path.regime,
                path.volatility_bucket,
                path.direction,
                path.horizon,
            )
            candidate = candidate_by_key.get(key)
            if candidate is None:
                continue
            ranked_items.append(
                SimpleNamespace(
                    score=cls._baseline_score(path.rank or count, count),
                    candidate=candidate,
                    path=path,
                )
            )

        scored = MarketContextShadowScoringServiceV011.rank(ranked_items, snapshot)
        by_key = {id(item): shadow for item, shadow in scored}
        result: list[TradingPathAnalysisV012] = []
        for item in ranked_items:
            path = item.path
            shadow = by_key.get(id(item))
            if shadow is None:
                result.append(path)
                continue
            context = TradingPathMarketContext(
                benchmark_id=getattr(snapshot, "benchmark_id", None),
                baseline_rank=shadow.baseline_rank,
                context_rank=shadow.context_rank,
                rank_delta=shadow.rank_delta,
                baseline_score=shadow.baseline_score,
                context_adjusted_score=shadow.context_adjusted_score,
                score_delta=shadow.score_delta,
                regime_compatibility=shadow.regime_compatibility,
                relative_strength_component=shadow.relative_strength_component,
                volatility_component=shadow.volatility_component,
            )
            result.append(replace(path, market_context=context))
            logger.warning(
                "[V012 PATH CONTEXT] ticker=%s hypothesis=%s baseline_rank=%d context_rank=%d rank_delta=%d baseline_score=%.4f context_score=%.4f score_delta=%.4f",
                path.ticker,
                path.hypothesis,
                shadow.baseline_rank,
                shadow.context_rank,
                shadow.rank_delta,
                shadow.baseline_score,
                shadow.context_adjusted_score,
                shadow.score_delta,
            )

        result.sort(key=lambda item: (item.market_context.context_rank is None, item.market_context.context_rank or 0, item.rank or 0))
        return tuple(result)


__all__ = ["TradingPathMarketContextServiceV012"]
