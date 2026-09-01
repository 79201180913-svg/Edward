from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from edward.domain import TradingPathAnalysisV012


@dataclass(frozen=True, slots=True)
class InstrumentOpportunityV013:
    """Consumer projection of canonical TradingPathAnalysisV012 results."""

    instrument_uid: str
    ticker: str
    decision: object
    current_state: object
    best_path: TradingPathAnalysisV012
    total_paths: int
    promoted_paths: int
    research_only_paths: int
    rejected_paths: int
    buy_paths: int
    wait_paths: int
    pass_paths: int


class TradingPathOpportunityConsumerV013:
    """Aggregate canonical trading paths without performing new analysis."""

    @staticmethod
    def _path_key(path: TradingPathAnalysisV012) -> tuple[int, float, float, str, int]:
        rank = path.rank if path.rank is not None else 10**9
        score = path.opportunity.score if path.opportunity.score is not None else float("-inf")
        confidence = path.opportunity.confidence if path.opportunity.confidence is not None else float("-inf")
        return (rank, -score, -confidence, path.hypothesis, path.horizon)

    @classmethod
    def build(cls, analyses: Iterable[TradingPathAnalysisV012]) -> tuple[InstrumentOpportunityV013, ...]:
        grouped: dict[tuple[str, str], list[TradingPathAnalysisV012]] = {}
        for analysis in analyses:
            grouped.setdefault((analysis.instrument_uid, analysis.ticker), []).append(analysis)

        results: list[InstrumentOpportunityV013] = []
        for (instrument_uid, ticker), paths in sorted(grouped.items()):
            ordered = tuple(sorted(paths, key=cls._path_key))
            best = ordered[0]
            statuses = Counter(str(path.status) for path in paths)
            decisions = Counter(str(path.decision) for path in paths)
            results.append(
                InstrumentOpportunityV013(
                    instrument_uid=instrument_uid,
                    ticker=ticker,
                    decision=best.decision,
                    current_state=best.current_state,
                    best_path=best,
                    total_paths=len(paths),
                    promoted_paths=statuses["promoted"],
                    research_only_paths=statuses["validated"] + statuses["discovered"] + statuses["promotable"],
                    rejected_paths=statuses["rejected"],
                    buy_paths=decisions["buy"],
                    wait_paths=decisions["wait"],
                    pass_paths=decisions["pass"],
                )
            )
        return tuple(results)


__all__ = ["InstrumentOpportunityV013", "TradingPathOpportunityConsumerV013"]
