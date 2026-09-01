from __future__ import annotations

import logging

from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathAnalysisV012,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathOpportunity,
    TradingPathCandidate,
    strategy_family_for_hypothesis,
)

logger = logging.getLogger(__name__)
TRADING_PATH_RANKING_SERVICE_VERSION = "0.8.12"


class TradingPathRankingServiceV012:
    """Rank discovered Trading Paths without producing a trading signal.

    Ranking is deliberately deterministic and uses only already available research
    evidence. Validation, market context, opportunity scoring and trading decisions
    remain separate stages.
    """

    @staticmethod
    def _sort_key(candidate: TradingPathCandidate) -> tuple[float, float, float, int, str, str, str, int]:
        evidence = candidate.evidence
        return (
            -evidence.excess_return_pct,
            -evidence.win_rate_pct,
            -evidence.median_forward_return_pct,
            -evidence.observations,
            candidate.rule.hypothesis,
            candidate.rule.regime,
            candidate.rule.volatility_bucket,
            candidate.rule.horizon,
        )

    @classmethod
    def rank(
        cls,
        candidates: tuple[TradingPathCandidate, ...] | list[TradingPathCandidate],
    ) -> tuple[TradingPathAnalysisV012, ...]:
        ordered = sorted(candidates, key=cls._sort_key)
        results: list[TradingPathAnalysisV012] = []

        for rank, candidate in enumerate(ordered, start=1):
            family = strategy_family_for_hypothesis(candidate.rule.hypothesis)
            if family is None:
                logger.warning(
                    "[V012 PATH RANKING] unknown hypothesis=%s ticker=%s; skipping",
                    candidate.rule.hypothesis,
                    candidate.rule.ticker,
                )
                continue

            results.append(
                TradingPathAnalysisV012(
                    instrument_uid=candidate.rule.instrument_uid,
                    ticker=candidate.rule.ticker,
                    strategy_family=family.value,
                    hypothesis=candidate.rule.hypothesis,
                    regime=candidate.rule.regime,
                    volatility_bucket=candidate.rule.volatility_bucket,
                    direction=candidate.rule.direction,
                    horizon=candidate.rule.horizon,
                    evidence=candidate.evidence,
                    opportunity=TradingPathOpportunity(),
                    current_state=TradingPathCurrentState.WAIT,
                    decision=TradingPathDecision.WAIT,
                    status=TradingPathAnalysisStatus.DISCOVERED,
                    rank=rank,
                )
            )

        logger.warning(
            "[V012 PATH RANKING] candidates=%d ranked=%d",
            len(candidates),
            len(results),
        )
        return tuple(results)


__all__ = ["TRADING_PATH_RANKING_SERVICE_VERSION", "TradingPathRankingServiceV012"]
