from __future__ import annotations

import logging

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryResult
from edward.services.trading_path_adaptive_discovery_service_v014 import AdaptiveDiscoveryCandidateV014, AdaptiveDiscoveryResultV014

logger = logging.getLogger(__name__)
TRADING_PATH_CANDIDATE_SERVICE_VERSION = "0.8.14"
ADAPTIVE_DISCOVERY_VERSION = "0.8.14"


class TradingPathCandidateServiceV014:
    """Unify fixed and adaptive research results into one candidate contract.

    The service does not validate or rank candidates. Both discovery sources become
    the same TradingPathCandidate type and therefore enter the same downstream path.
    Adaptive rule expressions are preserved in the hypothesis field until the domain
    rule contract gains a dedicated structured-condition field in the statistical
    integrity block.
    """

    SOURCE_FIXED = "fixed"
    SOURCE_ADAPTIVE = "adaptive"
    ADAPTIVE_HYPOTHESIS = "ADAPTIVE_RULE"
    ADAPTIVE_VOLATILITY = "Adaptive"
    ADAPTIVE_DIRECTION = "Positive"

    @staticmethod
    def _fixed_candidate(cell: ConditionalDiscoveryCell, *, instrument_uid: str, ticker: str) -> TradingPathCandidate:
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
            source_version="fixed:0.8.6",
        )

    @classmethod
    def _adaptive_candidate(cls, item: AdaptiveDiscoveryCandidateV014, *, instrument_uid: str, ticker: str) -> TradingPathCandidate:
        return TradingPathCandidate(
            rule=TradingPathRule(
                instrument_uid=instrument_uid,
                ticker=ticker,
                hypothesis=f"{cls.ADAPTIVE_HYPOTHESIS}:{item.rule.expression}",
                regime=item.rule.regime,
                volatility_bucket=cls.ADAPTIVE_VOLATILITY,
                direction=cls.ADAPTIVE_DIRECTION,
                horizon=item.rule.horizon,
            ),
            evidence=TradingPathEvidence(
                observations=item.observations,
                mean_forward_return_pct=item.mean_forward_return_pct,
                median_forward_return_pct=item.median_forward_return_pct,
                win_rate_pct=item.win_rate_pct,
                baseline_mean_return_pct=item.baseline_mean_return_pct,
                excess_return_pct=item.excess_return_pct,
                sufficient_sample=item.observations >= 12,
            ),
            source_version=ADAPTIVE_DISCOVERY_VERSION,
        )

    @classmethod
    def from_fixed(cls, result: ConditionalDiscoveryResult, *, instrument_uid: str, ticker: str) -> tuple[TradingPathCandidate, ...]:
        candidates = tuple(
            cls._fixed_candidate(cell, instrument_uid=instrument_uid, ticker=ticker)
            for evidence in result.evidence
            for cell in evidence.cells
            if cell.sufficient_sample and cell.excess_return_pct > 0.0
        )
        logger.warning(
            "[V014 CANDIDATE LAYER] source=fixed ticker=%s candidates=%d discovery_version=%s",
            ticker, len(candidates), getattr(result, "version", "unknown"),
        )
        return candidates

    @classmethod
    def from_adaptive(cls, result: AdaptiveDiscoveryResultV014, *, instrument_uid: str, ticker: str) -> tuple[TradingPathCandidate, ...]:
        candidates = tuple(
            cls._adaptive_candidate(item, instrument_uid=instrument_uid, ticker=ticker)
            for item in result.candidates
        )
        logger.warning(
            "[V014 CANDIDATE LAYER] source=adaptive ticker=%s candidates=%d discovery_version=%s",
            ticker, len(candidates), result.version,
        )
        return candidates

    @classmethod
    def combine(
        cls,
        fixed: tuple[TradingPathCandidate, ...] | list[TradingPathCandidate],
        adaptive: tuple[TradingPathCandidate, ...] | list[TradingPathCandidate],
        *,
        ticker: str,
    ) -> tuple[TradingPathCandidate, ...]:
        combined = tuple(fixed) + tuple(adaptive)
        logger.warning(
            "[V014 CANDIDATE LAYER RESULT] ticker=%s fixed=%d adaptive=%d total=%d",
            ticker, len(fixed), len(adaptive), len(combined),
        )
        return combined


__all__ = ["ADAPTIVE_DISCOVERY_VERSION", "TRADING_PATH_CANDIDATE_SERVICE_VERSION", "TradingPathCandidateServiceV014"]
