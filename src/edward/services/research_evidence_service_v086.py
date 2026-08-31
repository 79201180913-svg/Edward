from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, Sequence

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryResult
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult
from edward.services.wf_evidence_pipeline_v086 import WFEvidencePipelineResultV086, WFEvidencePipelineServiceV086

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ResearchEvidenceResultV086:
    """Instrument-level research evidence across all available WF contexts."""

    by_strategy: dict[str, WFEvidencePipelineResultV086]
    total_cells: int
    total_observations: int


class ResearchEvidenceServiceV086:
    """Aggregate conditional evidence across WF contexts without selecting a winner."""

    @classmethod
    def run(
        cls,
        *,
        ticker: str,
        conditional_discovery: ConditionalDiscoveryResult,
        wf_results: Mapping[str, RobustWalkForwardResult],
        candles: Sequence[Candle],
    ) -> ResearchEvidenceResultV086:
        by_strategy: dict[str, WFEvidencePipelineResultV086] = {}
        for strategy, wf_result in wf_results.items():
            by_strategy[strategy] = WFEvidencePipelineServiceV086.run(
                ticker=ticker,
                conditional_discovery=conditional_discovery,
                wf_result=wf_result,
                candles=candles,
            )

        total_cells = sum(len(item.evidence) for item in by_strategy.values())
        total_observations = sum(
            item.observations
            for pipeline in by_strategy.values()
            for item in pipeline.evidence
        )
        logger.warning(
            "[V086 RESEARCH EVIDENCE SUMMARY] ticker=%s strategies=%d cells=%d observations=%d",
            ticker,
            len(by_strategy),
            total_cells,
            total_observations,
        )
        return ResearchEvidenceResultV086(
            by_strategy=by_strategy,
            total_cells=total_cells,
            total_observations=total_observations,
        )


__all__ = ["ResearchEvidenceResultV086", "ResearchEvidenceServiceV086"]
