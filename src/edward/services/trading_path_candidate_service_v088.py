from __future__ import annotations

import logging
from typing import Iterable

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryResult

logger = logging.getLogger(__name__)
TRADING_PATH_CANDIDATE_SERVICE_VERSION = "0.8.8"


class TradingPathCandidateServiceV088:
    """Build research-only TradingPathCandidate objects from v0.8.6 evidence.

    Promotion here is deliberately limited to translating already-computed evidence.
    No thresholds are relaxed, no parameters are optimized, and no production decision
    is made. Statistical validation and independent backtesting remain later stages.
    """

    @staticmethod
    def _candidate(cell: ConditionalDiscoveryCell) -> TradingPathCandidate:
        return TradingPathCandidate(
            rule=TradingPathRule(
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
    def promote(cls, result: ConditionalDiscoveryResult) -> tuple[TradingPathCandidate, ...]:
        """Translate sufficient conditional cells into research candidates.

        The existing v0.8.6 contract says insufficient cells remain visible for audit
        but are not treated as evidence of an edge, so they are intentionally excluded
        from candidate promotion while remaining present in ``result``.
        """
        candidates = tuple(
            cls._candidate(cell)
            for evidence in result.evidence
            for cell in evidence.cells
            if cell.sufficient_sample
        )
        logger.warning(
            "[V088 TRADING PATH CANDIDATES] source_version=%s hypotheses=%d candidates=%d",
            result.version,
            len(result.evidence),
            len(candidates),
        )
        for candidate in candidates:
            logger.warning(
                "[V088 TRADING PATH CANDIDATE] hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d N=%d excess=%.6f sufficient=%s status=%s",
                candidate.rule.hypothesis,
                candidate.rule.regime,
                candidate.rule.volatility_bucket,
                candidate.rule.direction,
                candidate.rule.horizon,
                candidate.evidence.observations,
                candidate.evidence.excess_return_pct,
                candidate.evidence.sufficient_sample,
                candidate.status,
            )
        return candidates


__all__ = ["TRADING_PATH_CANDIDATE_SERVICE_VERSION", "TradingPathCandidateServiceV088"]
