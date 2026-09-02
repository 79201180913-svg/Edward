from __future__ import annotations

import logging
from typing import Sequence

from edward.domain import TradingPathAnalysisV012, TradingPathCandidate
from edward.services.analysis_service import Candle
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012
from edward.services.trading_path_ranking_service_v012 import TradingPathRankingServiceV012

logger = logging.getLogger(__name__)


class TradingPathAnalysisBuilderV012:
    """Build canonical path analysis from discovered candidates.

    Validation may target an explicit temporal range so the runtime can keep
    TRAIN discovery, VALIDATION selection and final OOS evaluation separate.
    """

    @classmethod
    def build(
        cls,
        candidates: Sequence[TradingPathCandidate],
        candles: Sequence[Candle],
        *,
        validation_windows: int = TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS,
        validation_test_size: int = TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE,
        validation_start: int | None = None,
        validation_end: int | None = None,
    ) -> tuple[TradingPathAnalysisV012, ...]:
        ranked = TradingPathRankingServiceV012.rank(tuple(candidates))
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

        result: list[TradingPathAnalysisV012] = []
        for path in ranked:
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
                logger.warning("[V012 PATH ANALYSIS] candidate lookup failed ticker=%s hypothesis=%s", path.ticker, path.hypothesis)
                continue

            validation = TradingPathOOSValidationServiceV012.build_validation(
                candidate,
                candles,
                windows=validation_windows,
                test_size=validation_test_size,
                evaluation_start=validation_start,
                evaluation_end=validation_end,
            )
            status = path.status
            if validation.validation.promotion_status == "validated":
                status = type(path.status).VALIDATED
            elif validation.validation.promotion_status == "rejected":
                status = type(path.status).REJECTED

            result.append(
                TradingPathAnalysisV012(
                    instrument_uid=path.instrument_uid,
                    ticker=path.ticker,
                    strategy_family=path.strategy_family,
                    hypothesis=path.hypothesis,
                    regime=path.regime,
                    volatility_bucket=path.volatility_bucket,
                    direction=path.direction,
                    horizon=path.horizon,
                    evidence=path.evidence,
                    validation=validation.validation,
                    market_context=path.market_context,
                    opportunity=path.opportunity,
                    current_state=path.current_state,
                    decision=path.decision,
                    status=status,
                    rank=path.rank,
                )
            )

        logger.warning(
            "[V012 PATH ANALYSIS] candidates=%d ranked=%d validated=%d rejected=%d validation_range=%s:%s",
            len(candidates), len(ranked),
            sum(item.status.value == "validated" for item in result),
            sum(item.status.value == "rejected" for item in result),
            validation_start, validation_end,
        )
        return tuple(result)


__all__ = ["TradingPathAnalysisBuilderV012"]
