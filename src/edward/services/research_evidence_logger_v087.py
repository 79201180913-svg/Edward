from __future__ import annotations

import logging
from typing import Iterable

from edward.services.research_evidence_report_v086 import ResearchEvidenceReportServiceV086, ResearchEvidenceRowV086
from edward.services.research_evidence_summary_v087 import ResearchEvidenceSummaryServiceV087, ResearchEvidenceSummaryV087


class ResearchEvidenceLoggerV087:
    """Build and log a bounded research report without touching trading decisions."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def build_and_log(
        self,
        evidence: Iterable,
        wf_evidence: Iterable = (),
        *,
        ticker: str,
        limit: int = 10,
        strategy_context: str = "Unknown",
    ) -> ResearchEvidenceSummaryV087:
        """Build a report while preserving the explicit strategy context contract."""
        rows: tuple[ResearchEvidenceRowV086, ...] = ResearchEvidenceReportServiceV086.build(
            evidence,
            wf_evidence,
            strategy_context=strategy_context,
        )
        summary = ResearchEvidenceSummaryServiceV087.build(rows, limit=limit)
        self.logger.warning(
            "[V087 RESEARCH SUMMARY] ticker=%s cells=%d interesting=%d low_sample=%d no_positive_excess=%d low_wf_persistence=%d top_magnitude=%d top_consistency=%d top_stability=%d strategy=%s",
            ticker, summary.total_cells, summary.interesting, summary.low_sample,
            summary.no_positive_excess, summary.low_wf_persistence,
            len(summary.top_magnitude), len(summary.top_consistency), len(summary.top_stability),
            strategy_context,
        )
        for rank, row in enumerate(summary.top_magnitude, 1):
            self.logger.warning(
                "[V087 RESEARCH MAGNITUDE] ticker=%s rank=%d strategy=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d excess=%.6f N=%d flag=%s",
                ticker, rank, row.strategy_context, row.evidence.hypothesis, row.evidence.regime,
                row.evidence.volatility_bucket, row.evidence.direction, row.evidence.horizon,
                row.evidence.excess_return_pct, row.evidence.observations, row.research_flag,
            )
        for rank, row in enumerate(summary.top_consistency, 1):
            self.logger.warning(
                "[V087 RESEARCH CONSISTENCY] ticker=%s rank=%d strategy=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d win_rate=%.2f N=%d flag=%s",
                ticker, rank, row.strategy_context, row.evidence.hypothesis, row.evidence.regime,
                row.evidence.volatility_bucket, row.evidence.direction, row.evidence.horizon,
                row.evidence.win_rate_pct, row.evidence.observations, row.research_flag,
            )
        for rank, row in enumerate(summary.top_stability, 1):
            self.logger.warning(
                "[V087 RESEARCH STABILITY] ticker=%s rank=%d strategy=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d wf_persistence=%.2f wf_windows=%d N=%d flag=%s",
                ticker, rank, row.strategy_context, row.evidence.hypothesis, row.evidence.regime,
                row.evidence.volatility_bucket, row.evidence.direction, row.evidence.horizon,
                row.wf.wf_persistence_pct, row.wf.wf_windows, row.evidence.observations, row.research_flag,
            )
        return summary


__all__ = ["ResearchEvidenceLoggerV087"]
