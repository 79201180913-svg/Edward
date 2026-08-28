from __future__ import annotations

from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.forecast_quality_service_v08 import ForecastQualityResult, ForecastQualityService
from edward.services.forecast_service import ForecastService


class ForecastQualityAdapterV08:
    """Evaluate the existing ForecastService without changing its public result contract."""

    def __init__(self, forecast_service: type[ForecastService] = ForecastService, quality_service: type[ForecastQualityService] = ForecastQualityService) -> None:
        self._forecast_service = forecast_service
        self._quality_service = quality_service

    def evaluate(
        self,
        *,
        candles: Sequence[Candle],
        horizons: Sequence[int],
    ) -> ForecastQualityResult:
        def forecast(history: Sequence[Candle], horizon: int) -> tuple[float, float]:
            result = self._forecast_service.forecast(
                instrument_uid="quality-eval",
                ticker="QUALITY-EVAL",
                candles=history,
                horizons=(horizon,),
            )
            point = result.point(horizon)
            return point.expected_price, point.probability_up

        return self._quality_service.evaluate(
            candles=candles,
            horizons=horizons,
            forecast_fn=forecast,
            min_history=max(self._forecast_service.MIN_CANDLES, self._quality_service.MIN_ORIGIN_OBSERVATIONS),
        )
