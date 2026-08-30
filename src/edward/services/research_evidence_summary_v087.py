from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from edward.services.research_evidence_report_v086 import ResearchEvidenceRowV086


@dataclass(frozen=True, slots=True)
class ResearchEvidenceSummaryV087:
    total_cells: int
    interesting: int
    low_sample: int
    no_positive_excess: int
    low_wf_persistence: int
    top_magnitude: tuple[ResearchEvidenceRowV086, ...]
    top_consistency: tuple[ResearchEvidenceRowV086, ...]
    top_stability: tuple[ResearchEvidenceRowV086, ...]


class ResearchEvidenceSummaryServiceV087:
    """Produce bounded research views; never selects a trading strategy."""

    @classmethod
    def build(cls, rows: Iterable[ResearchEvidenceRowV086], limit: int = 10) -> ResearchEvidenceSummaryV087:
        items = tuple(rows)
        limit = max(1, limit)
        return ResearchEvidenceSummaryV087(
            total_cells=len(items),
            interesting=sum(row.research_flag == "INTERESTING" for row in items),
            low_sample=sum(row.research_flag == "LOW_SAMPLE" for row in items),
            no_positive_excess=sum(row.research_flag == "NO_POSITIVE_EXCESS" for row in items),
            low_wf_persistence=sum(row.research_flag == "LOW_WF_PERSISTENCE" for row in items),
            top_magnitude=tuple(sorted(items, key=lambda row: row.evidence.excess_return_pct, reverse=True)[:limit]),
            top_consistency=tuple(sorted(items, key=lambda row: row.evidence.win_rate_pct, reverse=True)[:limit]),
            top_stability=tuple(sorted((row for row in items if row.wf is not None), key=lambda row: row.wf.wf_persistence_pct, reverse=True)[:limit]),
        )


__all__ = ["ResearchEvidenceSummaryV087", "ResearchEvidenceSummaryServiceV087"]
