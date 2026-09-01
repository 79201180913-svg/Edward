from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from edward.domain import TradingPathAnalysisV012

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TradingPathPipelineDiagnosticV012:
    ticker: str
    hypothesis: str
    regime: str
    volatility_bucket: str
    direction: str
    horizon: int
    rank: int | None
    validation_status: str | None
    opportunity_score: float | None
    opportunity_confidence: float | None
    expected_value_pct: float | None
    risk_score: float | None
    risk_gate: bool | None
    decision: str
    decision_reason: str | None


class TradingPathPipelineDiagnosticsServiceV012:
    @staticmethod
    def collect(analyses: Iterable[TradingPathAnalysisV012]) -> tuple[TradingPathPipelineDiagnosticV012, ...]:
        rows: list[TradingPathPipelineDiagnosticV012] = []
        for analysis in analyses:
            opportunity = analysis.opportunity
            validation = analysis.validation
            reason = None
            if analysis.decision is not None:
                if hasattr(analysis.decision, "value"):
                    reason = analysis.decision.value
                else:
                    reason = str(analysis.decision)
            row = TradingPathPipelineDiagnosticV012(
                ticker=analysis.ticker,
                hypothesis=analysis.hypothesis,
                regime=analysis.regime,
                volatility_bucket=analysis.volatility_bucket,
                direction=analysis.direction,
                horizon=analysis.horizon,
                rank=analysis.rank,
                validation_status=getattr(validation, "promotion_status", None) if validation is not None else None,
                opportunity_score=opportunity.score if opportunity else None,
                opportunity_confidence=opportunity.confidence if opportunity else None,
                expected_value_pct=opportunity.expected_value_pct if opportunity else None,
                risk_score=opportunity.risk_score if opportunity else None,
                risk_gate=opportunity.risk_gate if opportunity else None,
                decision=analysis.decision.value if hasattr(analysis.decision, "value") else str(analysis.decision),
                decision_reason=reason,
            )
            rows.append(row)
            logger.warning(
                "[V012 PATH DECISION] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d rank=%s validation=%s ev=%s risk=%s risk_gate=%s opportunity=%s confidence=%s decision=%s reason=%s",
                row.ticker, row.hypothesis, row.regime, row.volatility_bucket, row.direction, row.horizon,
                row.rank, row.validation_status, row.expected_value_pct, row.risk_score, row.risk_gate,
                row.opportunity_score, row.opportunity_confidence, row.decision, row.decision_reason,
            )
        return tuple(rows)


__all__ = ["TradingPathPipelineDiagnosticV012", "TradingPathPipelineDiagnosticsServiceV012"]
