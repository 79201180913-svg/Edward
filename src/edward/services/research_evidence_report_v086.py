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
    ) -> tuple[ResearchEvidenceRowV086, ...]:
        evidence_list = list(evidence)
        wf_by_key = {
            (item.hypothesis, item.regime, item.volatility_bucket, item.direction, item.horizon): item
            for item in wf_evidence
        }
        magnitude = [item.excess_return_pct for item in evidence_list]
        consistency = [item.win_rate_pct for item in evidence_list]
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
                    stability_rank=(cls._rank_desc([x.wf_persistence_pct for x in wf_evidence], wf.wf_persistence_pct) if wf is not None and list(wf_evidence) else 0),
                    research_flag=flag,
                )
            )
        return tuple(rows)


__all__ = ["ResearchEvidenceRowV086", "ResearchEvidenceReportServiceV086"]
