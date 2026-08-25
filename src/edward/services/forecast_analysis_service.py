from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.forecast_service import ForecastResult, ForecastService


@dataclass(frozen=True, slots=True)
class ForecastAwareAnalysis:
    analysis: AnalysisResult
    forecast: ForecastResult


class ForecastAnalysisService:
    """Compose the existing v0.4 strategy analysis with the v0.5 Forecast Engine."""

    def __init__(self, analysis_service=None, forecast_service: type[ForecastService] = ForecastService):
        from edward.services.analysis_service import AnalysisService

        self.analysis = analysis_service or AnalysisService()
        self.forecast_service = forecast_service

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
    ) -> ForecastAwareAnalysis:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        analysis = self.analysis.analyze(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=ordered,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
        )
        forecast = self.forecast_service.forecast(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=ordered,
        )
        return ForecastAwareAnalysis(analysis=analysis, forecast=forecast)
