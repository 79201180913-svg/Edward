from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015
from edward.services.opportunity_analysis_pipeline_v0821 import OpportunityAnalysisPipelineV0821


OPPORTUNITY_AB_DIAGNOSTICS_V015_VERSION = "0.8.15"


@dataclass(frozen=True, slots=True)
class OpportunityABMetricsV015:
    source: str
    instruments: int
    analyzed: int
    analysis_unavailable: int
    path_count: int
    adaptive_paths: int
    fixed_paths: int
    buy: int
    wait: int
    pass_count: int
    average_opportunity_score: float


@dataclass(frozen=True, slots=True)
class OpportunityABComparisonV015:
    legacy: OpportunityABMetricsV015
    canonical: OpportunityABMetricsV015

    @property
    def coverage_delta(self) -> int:
        return self.canonical.analyzed - self.legacy.analyzed

    @property
    def path_delta(self) -> int:
        return self.canonical.path_count - self.legacy.path_count

    @property
    def adaptive_paths_added(self) -> int:
        return self.canonical.adaptive_paths

    @property
    def buy_delta(self) -> int:
        return self.canonical.buy - self.legacy.buy


class OpportunityABDiagnosticsV015:
    """Diagnostic-only A/B comparison for legacy vs canonical Opportunities."""

    @staticmethod
    def summarize(
        source: str,
        results: Iterable[Any],
    ) -> OpportunityABMetricsV015:
        items = tuple(results)
        scores = [float(getattr(item, "opportunity_score", 0.0) or 0.0) for item in items]
        decisions = Counter(str(getattr(item, "decision", "")).lower() for item in items)
        canonical = [getattr(item, "canonical_opportunity", None) for item in items]
        analyses = [item for item in canonical if item is not None]
        paths = [path for view in analyses for path in getattr(view, "canonical_results", ())]
        adaptive = sum(
            1
            for path in paths
            if str(getattr(path, "hypothesis", "")).startswith("ADAPTIVE_RULE:")
        )
        fixed = len(paths) - adaptive
        unavailable = sum(
            1
            for item in items
            if str(getattr(item, "status", "")).upper() in {"ANALYSIS_UNAVAILABLE", "ERROR"}
        )
        return OpportunityABMetricsV015(
            source=source,
            instruments=len(items),
            analyzed=len(analyses),
            analysis_unavailable=unavailable,
            path_count=len(paths),
            adaptive_paths=adaptive,
            fixed_paths=fixed,
            buy=decisions["buy"],
            wait=decisions["wait"],
            pass_count=decisions["pass"],
            average_opportunity_score=(sum(scores) / len(scores)) if scores else 0.0,
        )

    @staticmethod
    def compare(
        legacy_results: Iterable[Any],
        canonical_results: Iterable[Any],
    ) -> OpportunityABComparisonV015:
        return OpportunityABComparisonV015(
            legacy=OpportunityABDiagnosticsV015.summarize("legacy", legacy_results),
            canonical=OpportunityABDiagnosticsV015.summarize("canonical", canonical_results),
        )


__all__ = [
    "OPPORTUNITY_AB_DIAGNOSTICS_V015_VERSION",
    "OpportunityABMetricsV015",
    "OpportunityABComparisonV015",
    "OpportunityABDiagnosticsV015",
]
