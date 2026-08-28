from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.forecast_quality_adapter_v08 import ForecastQualityAdapterV08


def _candles(count: int = 160) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    result: list[Candle] = []
    for index in range(count):
        price *= 1.0 + (0.001 if index % 7 else -0.002)
        result.append(Candle(start + timedelta(days=index), price, price, price, price))
    return result


def test_adapter_evaluates_existing_forecast_service():
    result = ForecastQualityAdapterV08().evaluate(candles=_candles(), horizons=(1, 5))
    assert result.version == "0.8.0"
    assert {item.horizon_days for item in result.points} == {1, 5}
    assert all(item.observations > 0 for item in result.points)
