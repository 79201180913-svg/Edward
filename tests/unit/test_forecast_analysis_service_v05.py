from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.forecast_analysis_service import ForecastAnalysisService


def _candles(count: int = 220) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    result = []
    for index in range(count):
        price *= 1.002 if index % 7 else 0.999
        result.append(
            Candle(
                timestamp=start + timedelta(days=index),
                open=price * 0.999,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=1000 + index,
            )
        )
    return result


def test_forecast_aware_analysis_contains_strategy_analysis_and_forecast():
    result = ForecastAnalysisService().analyze(
        instrument_uid="uid-1",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    assert result.analysis.instrument_uid == "uid-1"
    assert result.analysis.ticker == "TEST"
    assert len(result.analysis.strategies) == 4
    assert result.forecast.instrument_uid == "uid-1"
    assert result.forecast.ticker == "TEST"
    assert result.forecast.point(5).horizon_days == 5
