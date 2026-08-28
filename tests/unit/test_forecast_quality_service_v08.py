from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.forecast_quality_service_v08 import ForecastQualityService


def _candles(count: int = 180) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(days=index), value, value, value, value)
        for index, value in enumerate(100.0 + index * 0.5 for index in range(count))
    ]


def test_forecast_quality_is_point_in_time_and_reports_directional_accuracy():
    candles = _candles()

    def forecast(history, horizon):
        current = history[-1].close
        return current + 0.5 * horizon, 100.0

    result = ForecastQualityService.evaluate(
        candles=candles,
        horizons=(1, 5),
        forecast_fn=forecast,
    )

    assert result.version == "0.8.0"
    assert {item.horizon_days for item in result.points} == {1, 5}
    assert all(item.observations > 0 for item in result.points)
    assert all(item.directional_accuracy_pct > 95.0 for item in result.points)


def test_calibration_exposes_observed_frequency_against_forecast_probability():
    candles = _candles()

    def forecast(history, horizon):
        current = history[-1].close
        return current + 0.1, 70.0

    result = ForecastQualityService.evaluate(
        candles=candles,
        horizons=(1,),
        forecast_fn=forecast,
        calibration_bins=(0.0, 60.0, 80.0, 100.0),
    )

    assert result.calibration
    assert any(item.observations > 0 for item in result.calibration)
    assert all(0.0 <= item.observed_positive_pct <= 100.0 for item in result.calibration)
    assert all(item.calibration_error_pct >= 0.0 for item in result.calibration)


def test_insufficient_history_is_rejected():
    candles = _candles(20)
    try:
        ForecastQualityService.evaluate(
            candles=candles,
            horizons=(5,),
            forecast_fn=lambda history, horizon: (history[-1].close, 50.0),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Forecast quality must reject insufficient history")
