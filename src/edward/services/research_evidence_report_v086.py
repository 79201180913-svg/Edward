from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from edward.services.evidence_audit_service_v086 import EvidenceAuditV086, WFAwareEvidenceAuditV086


@dataclass(frozen=True, slots=True)
class ResearchEvidenceRowV086:
    evidence: EvidenceAuditV086
    wf: WFAwareEvidenceAuditV086 | None
    magnitude_rank: int
    consistency_rank: int
    stability_rank: int
    research_flag: str
    strategy_context: str | None = None


class ResearchEvidenceReportServiceV086:
    """Rank research evidence without turning it into a trading decision."""

    @staticmethod
    def _rank_desc(values: list[float], value: float) -> int:
        ordered = sorted(values, reverse=True)
        return ordered.index(value) + 1

    @classmethod
    def build(
        cls,
        evidence: Iterable[EvidenceAuditV086],
        wf_evidence: Iterable[WFAwareEvidenceAuditV086] = (),
        *,
        strategy_context: str | None = None,
    ) -> tuple[ResearchEvidenceRowV086, ...]:
        """Build a report for exactly one WF strategy context."""
        if strategy_context is None:
            raise ValueError("strategy_context is required for a single-context report")
        evidence_list = list(evidence)
        wf_list = list(wf_evidence)
        wf_by_key = {
            (item.hypothesis, item.regime, item.volatility_bucket, item.direction, item.horizon): item
            for item in wf_list
        }
        magnitude = [item.excess_return_pct for item in evidence_list]
        consistency = [item.win_rate_pct for item in evidence_list]
        stability = [item.wf_persistence_pct for item in wf_list]
        rows: list[ResearchEvidenceRowV086] = []
        for item in evidence_list:
            key = (item.hypothesis, item.regime, item.volatility_bucket, item.direction, item.horizon)
            wf = wf_by_key.get(key)
            if not item.sufficient_sample:
                flag = "LOW_SAMPLE"
            elif item.excess_return_pct <= 0:
                flag = "NO_POSITIVE_EXCESS"
            elif wf is not None and wf.wf_persistence_pct < 50.0:
                flag = "LOW_WF_PERSISTENCE"
            else:
                flag = "INTERESTING"
            rows.append(
                ResearchEvidenceRowV086(
                    evidence=item,
                    wf=wf,
                    magnitude_rank=cls._rank_desc(magnitude, item.excess_return_pct),
                    consistency_rank=cls._rank_desc(consistency, item.win_rate_pct),
                    stability_rank=cls._rank_desc(stability, wf.wf_persistence_pct) if wf is not None and stability else 0,
                    research_flag=flag,
                    strategy_context=strategy_context,
                )
            )
        return tuple(rows)

    @classmethod
    def build_from_wf_contexts(
        cls,
        evidence: Iterable[EvidenceAuditV086],
        wf_contexts: Iterable[tuple[str, Iterable[WFAwareEvidenceAuditV086]]],
    ) -> tuple[ResearchEvidenceRowV086, ...]:
        """Retain one report row per strategy/WF context; never overwrite a key."""
        evidence_list = tuple(evidence)
        rows: list[ResearchEvidenceRowV086] = []
        for strategy, audits in wf_contexts:
            rows.extend(cls.build(evidence_list, audits, strategy_context=strategy))
        return tuple(rows)


__all__ = ["ResearchEvidenceRowV086", "ResearchEvidenceReportServiceV086"]
