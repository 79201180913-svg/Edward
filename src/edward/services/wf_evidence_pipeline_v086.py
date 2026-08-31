from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryResult
from edward.services.evidence_audit_service_v086 import EvidenceAuditServiceV086, WFAwareEvidenceAuditV086
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WFEvidencePipelineResultV086:
    evidence: tuple[WFAwareEvidenceAuditV086, ...]
    source_wf_strategy: str
    source_wf_windows: int


class WFEvidencePipelineServiceV086:
    """Build WF-aware research evidence without touching production decisions."""

    @classmethod
    def run(
        cls,
        *,
        ticker: str,
        conditional_discovery: ConditionalDiscoveryResult,
        wf_result: RobustWalkForwardResult,
        candles: Sequence[Candle],
    ) -> WFEvidencePipelineResultV086:
        evidence = EvidenceAuditServiceV086.audit_wf(conditional_discovery, wf_result, candles)
        for item in evidence:
            logger.warning(
                "[V086 WF EVIDENCE] ticker=%s strategy_context=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d wf_windows=%d positive_wf_windows=%d negative_wf_windows=%d wf_persistence=%.2f observations=%d",
                ticker,
                wf_result.strategy,
                item.hypothesis,
                item.regime,
                item.volatility_bucket,
                item.direction,
                item.horizon,
                item.wf_windows,
                item.positive_wf_windows,
                item.negative_wf_windows,
                item.wf_persistence_pct,
                item.observations,
            )
        logger.warning(
            "[V086 WF EVIDENCE SUMMARY] ticker=%s strategy_context=%s cells=%d wf_windows=%d",
            ticker,
            wf_result.strategy,
            len(evidence),
            len(wf_result.windows),
        )
        return WFEvidencePipelineResultV086(
            evidence=evidence,
            source_wf_strategy=wf_result.strategy,
            source_wf_windows=len(wf_result.windows),
        )


__all__ = ["WFEvidencePipelineResultV086", "WFEvidencePipelineServiceV086"]
