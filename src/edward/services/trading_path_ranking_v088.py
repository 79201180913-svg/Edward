from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from edward.domain import TradingPathCandidate


@dataclass(frozen=True, slots=True)
class RankedTradingPathV088:
    candidate: TradingPathCandidate
    score: float


class TradingPathRankingServiceV088:
    """Rank and deterministically deduplicate research candidates.

    Ranking is research prioritization only. It never changes candidate status
    and never bypasses Walk Forward, robustness, Quality Gate, or execution.
    """

    @staticmethod
    def _key(candidate: TradingPathCandidate) -> tuple[str, str, str, str, str, int]:
        rule = candidate.rule
        return (
            rule.instrument_uid,
            rule.hypothesis,
            rule.regime,
            rule.volatility_bucket,
            rule.direction,
            rule.horizon,
        )

    @staticmethod
    def _score(candidate: TradingPathCandidate) -> float:
        evidence = candidate.evidence
        persistence = evidence.wf_persistence_pct or 0.0
        sample_bonus = min(evidence.observations, 100) / 100.0
        return evidence.excess_return_pct * (1.0 + persistence / 100.0) * (0.5 + sample_bonus)

    @classmethod
    def rank_and_deduplicate(cls, candidates: Iterable[TradingPathCandidate]) -> tuple[RankedTradingPathV088, ...]:
        best: dict[tuple[str, str, str, str, str, int], RankedTradingPathV088] = {}
        for candidate in candidates:
            ranked = RankedTradingPathV088(candidate, cls._score(candidate))
            key = cls._key(candidate)
            previous = best.get(key)
            if previous is None or ranked.score > previous.score:
                best[key] = ranked
        return tuple(sorted(best.values(), key=lambda item: (-item.score, cls._key(item.candidate))))


__all__ = ["RankedTradingPathV088", "TradingPathRankingServiceV088"]
