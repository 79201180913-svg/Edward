from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.entry_quality_integration_v082 import EntryQualityIntegrationResult
from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisResult
from edward.services.opportunity_adjustment_service_v082 import OpportunityAdjustmentResult


@dataclass(frozen=True, slots=True)
class InstrumentAnalysisResultV082:
    """Unified analytical view; it does not allocate capital or make decisions."""

    instrument_uid: str
    ticker: str
    fundamental: FundamentalAnalysisResult
    market: Any
    risk: Any
    entry_quality: EntryQualityIntegrationResult
    opportunity: Any
    opportunity_adjustment: OpportunityAdjustmentResult | None
    overall_score: float
    confidence: float
    coverage: float
    status: str
    reason_codes: tuple[str, ...] = ()

    @classmethod
    def from_pipeline(cls, *, instrument_uid: str, ticker: str, pipeline_result: Any) -> "InstrumentAnalysisResultV082":
        fundamental = pipeline_result.fundamental
        base = pipeline_result.base
        analysis = getattr(base, "analysis", None)
        opportunity = getattr(base, "opportunity", None)
        risk = getattr(opportunity, "risk", None)
        market = {
            "regime": getattr(analysis, "market_regime", None),
            "trend": getattr(analysis, "trend", None),
            "momentum": getattr(analysis, "momentum", None),
        }
        entry_quality = pipeline_result.entry_quality
        adjusted = pipeline_result.opportunity_adjustment
        opportunity_score = getattr(adjusted.opportunity, "score", None) if adjusted else getattr(opportunity, "score", 0.0)
        confidence = min(100.0, max(0.0, (float(fundamental.confidence) + float(getattr(base, "confidence", 0.0))) / 2.0))
        coverage = float(fundamental.coverage)
        reasons = tuple(fundamental.reason_codes) + tuple(entry_quality.reason_codes) + (tuple(adjusted.reason_codes) if adjusted else ())
        status = "UNAVAILABLE" if fundamental.status == "UNAVAILABLE" else "PARTIAL" if coverage < 100.0 else "AVAILABLE"
        return cls(
            instrument_uid=instrument_uid,
            ticker=ticker,
            fundamental=fundamental,
            market=market,
            risk=risk,
            entry_quality=entry_quality,
            opportunity=opportunity,
            opportunity_adjustment=adjusted,
            overall_score=float(opportunity_score or 0.0),
            confidence=confidence,
            coverage=coverage,
            status=status,
            reason_codes=reasons,
        )


__all__ = ["InstrumentAnalysisResultV082"]
