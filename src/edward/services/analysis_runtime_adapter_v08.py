from __future__ import annotations

from typing import Any, Iterable

from edward.services.analysis_service import AnalysisResult, Candle, AnalysisService
from edward.services.analysis_pipeline_service_v08_fixed import AnalysisPipelineServiceV08


class AnalysisRuntimeAdapterV08:
    """Expose corrected v0.8 analysis behind a stable runtime-facing method."""

    def __init__(self, *, enabled: bool = True, legacy_service: AnalysisService | None = None) -> None:
        self.enabled = enabled
        self.legacy_service = legacy_service or AnalysisService()
        self.v08_service = AnalysisPipelineServiceV08()

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
    ) -> AnalysisResult:
        if not self.enabled:
            return self.legacy_service.analyze(
                instrument_uid=instrument_uid,
                ticker=ticker,
                candles=candles,
                profile=profile,
                risk_profile=risk_profile,
                horizon=horizon,
            )
        return self.v08_service.analyze(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=candles,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
        ).analysis


__all__ = ["AnalysisRuntimeAdapterV08"]
