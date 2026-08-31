from __future__ import annotations

import logging

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryResult

logger = logging.getLogger(__name__)
TRADING_PATH_CANDIDATE_SERVICE_VERSION = "0.8.8"


class TradingPathCandidateServiceV088:
    """Build research-only TradingPathCandidate objects from v0.8.6 evidence."""

    @staticmethod
    def _candidate(cell: ConditionalDiscoveryCell, *, instrument_uid: str, ticker: str) -> TradingPathCandidate:
        return TradingPathCandidate(
            rule=TradingPathRule(
                instrument_uid=instrument_uid,
                ticker=ticker,
                hypothesis=cell.hypothesis,
                regime=cell.regime,
                volatility_bucket=cell.volatility_bucket,
                direction=cell.direction,
                horizon=cell.horizon,
            ),
            evidence=TradingPathEvidence(
                observations=cell.observations,
                mean_forward_return_pct=cell.mean_forward_return_pct,
                median_forward_return_pct=cell.median_forward_return_pct,
                win_rate_pct=cell.win_rate_pct,
                baseline_mean_return_pct=cell.baseline_mean_return_pct,
                excess_return_pct=cell.excess_return_pct,
                sufficient_sample=cell.sufficient_sample,
            ),
        )

    @classmethod
    def promote(
        cls,
        result: ConditionalDiscoveryResult,
        *,
        instrument_uid: str,
        ticker: str,
    ) -> tuple[TradingPathCandidate, ...]:
        """Promote only sufficient cells with positive excess into research candidates.

        Insufficient cells remain visible in the original discovery result. Negative or
        zero excess is not a candidate because it does not describe a positive conditional
        opportunity. Candidates remain RESEARCH-only until later validation stages.
        """
        candidates = tuple(
            cls._candidate(cell, instrument_uid=instrument_uid, ticker=ticker)
            for evidence in result.evidence
            for cell in evidence.cells
            if cell.sufficient_sample and cell.excess_return_pct > 0.0
        )
        logger.warning(
            "[V088 TRADING PATH CANDIDATES] source_version=%s ticker=%s hypotheses=%d candidates=%d",
            result.version,
            ticker,
            len(result.evidence),
            len(candidates),
        )
        for candidate in candidates:
            logger.warning(
                "[V088 TRADING PATH CANDIDATE] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d N=%d excess=%.6f status=%s",
                ticker,
                candidate.rule.hypothesis,
                candidate.rule.regime,
                candidate.rule.volatility_bucket,
                candidate.rule.direction,
                candidate.rule.horizon,
                candidate.evidence.observations,
                candidate.evidence.excess_return_pct,
                candidate.status,
            )
        return candidates


__all__ = ["TRADING_PATH_CANDIDATE_SERVICE_VERSION", "TradingPathCandidateServiceV088"]
