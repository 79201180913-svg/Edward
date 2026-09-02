from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Mapping

from edward.domain import TradingPathCandidate
from edward.services.trading_path_statistical_integrity_service_v014 import (
    StatisticalIntegrityResultV014,
)

logger = logging.getLogger(__name__)
CANDIDATE_PRUNING_VERSION = "0.8.14"


@dataclass(frozen=True, slots=True)
class CandidatePruningConfigV014:
    """Deterministic TRAIN-only pruning limits for adaptive candidates."""

    min_adaptive_observations: int = 12
    min_adaptive_excess_return_pct: float = 0.0
    max_adaptive_conditions: int = 3
    max_adaptive_per_context: int = 5
    require_statistical_integrity: bool = False


class TradingPathCandidatePruningServiceV014:
    """Prune weak/duplicated adaptive candidates before expensive validation.

    Fixed candidates are never removed here. Adaptive pruning uses discovery evidence
    only; OOS returns, walk-forward persistence and quality-gate outputs are not
    consulted. When statistical integrity results are supplied and explicitly enabled,
    every adaptive candidate must also pass the shared TRAIN/VALIDATION family-wise
    statistical control before it can continue downstream.
    """

    ADAPTIVE_PREFIX = "ADAPTIVE_RULE:"
    _CONDITION_RE = re.compile(r"\s+AND\s+")

    @classmethod
    def _is_adaptive(cls, candidate: TradingPathCandidate) -> bool:
        return candidate.rule.hypothesis.upper().startswith(cls.ADAPTIVE_PREFIX)

    @classmethod
    def _condition_count(cls, candidate: TradingPathCandidate) -> int:
        expression = candidate.rule.hypothesis[len(cls.ADAPTIVE_PREFIX):]
        if not expression.strip():
            return 0
        return len(cls._CONDITION_RE.split(expression))

    @classmethod
    def _adaptive_key(cls, candidate: TradingPathCandidate) -> tuple[str, str, int, str]:
        rule = candidate.rule
        return (rule.regime, rule.volatility_bucket, rule.horizon, rule.hypothesis.upper())

    @classmethod
    def _context_key(cls, candidate: TradingPathCandidate) -> tuple[str, str, int]:
        rule = candidate.rule
        return (rule.regime, rule.volatility_bucket, rule.horizon)

    @staticmethod
    def _rank_key(candidate: TradingPathCandidate) -> tuple[float, float, float, int, str]:
        evidence = candidate.evidence
        return (
            -evidence.excess_return_pct,
            -evidence.win_rate_pct,
            -evidence.median_forward_return_pct,
            -evidence.observations,
            candidate.rule.hypothesis,
        )

    @classmethod
    def prune(
        cls,
        candidates: tuple[TradingPathCandidate, ...] | list[TradingPathCandidate],
        *,
        config: CandidatePruningConfigV014 | None = None,
        statistical_integrity: Mapping[TradingPathCandidate, StatisticalIntegrityResultV014] | None = None,
    ) -> tuple[TradingPathCandidate, ...]:
        cfg = config or CandidatePruningConfigV014()
        if cfg.min_adaptive_observations < 1:
            raise ValueError("min_adaptive_observations must be >= 1")
        if cfg.max_adaptive_conditions < 1:
            raise ValueError("max_adaptive_conditions must be >= 1")
        if cfg.max_adaptive_per_context < 1:
            raise ValueError("max_adaptive_per_context must be >= 1")
        if cfg.require_statistical_integrity and statistical_integrity is None:
            raise ValueError("statistical_integrity is required when require_statistical_integrity=True")

        fixed = [candidate for candidate in candidates if not cls._is_adaptive(candidate)]
        adaptive = [candidate for candidate in candidates if cls._is_adaptive(candidate)]

        retained: list[TradingPathCandidate] = []
        dropped_insufficient = 0
        dropped_excess = 0
        dropped_complex = 0
        dropped_duplicate = 0
        dropped_statistical = 0

        seen: set[tuple[str, str, int, str]] = set()
        eligible: list[TradingPathCandidate] = []
        for candidate in adaptive:
            evidence = candidate.evidence
            if evidence.observations < cfg.min_adaptive_observations:
                dropped_insufficient += 1
                continue
            if evidence.excess_return_pct <= cfg.min_adaptive_excess_return_pct:
                dropped_excess += 1
                continue
            if cls._condition_count(candidate) > cfg.max_adaptive_conditions:
                dropped_complex += 1
                continue
            key = cls._adaptive_key(candidate)
            if key in seen:
                dropped_duplicate += 1
                continue
            seen.add(key)
            if cfg.require_statistical_integrity:
                integrity = statistical_integrity.get(candidate)
                if integrity is None or not integrity.statistically_valid:
                    dropped_statistical += 1
                    continue
            eligible.append(candidate)

        by_context: dict[tuple[str, str, int], list[TradingPathCandidate]] = {}
        for candidate in eligible:
            by_context.setdefault(cls._context_key(candidate), []).append(candidate)

        for context in sorted(by_context):
            ranked = sorted(by_context[context], key=cls._rank_key)
            retained.extend(ranked[: cfg.max_adaptive_per_context])

        # Preserve the quality-ranked order produced by pruning. Downstream consumers
        # may rely on deterministic ranking; do not re-sort alphabetically here.
        result = tuple(fixed) + tuple(retained)
        logger.warning(
            "[V014 CANDIDATE PRUNING] input=%d fixed=%d adaptive=%d retained=%d "
            "dropped_insufficient=%d dropped_excess=%d dropped_complex=%d "
            "dropped_duplicate=%d dropped_statistical=%d statistical_gate=%s version=%s train_only=True",
            len(candidates), len(fixed), len(adaptive), len(result),
            dropped_insufficient, dropped_excess, dropped_complex, dropped_duplicate,
            dropped_statistical, cfg.require_statistical_integrity, CANDIDATE_PRUNING_VERSION,
        )
        return result


__all__ = ["CANDIDATE_PRUNING_VERSION", "CandidatePruningConfigV014", "TradingPathCandidatePruningServiceV014"]
