from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.point_in_time_validation_service import PointInTimeValidationService


def candles_from_closes(closes: list[float]) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(days=i), value, value * 1.01, value * 0.99, value, 1000 + i)
        for i, value in enumerate(closes)
    ]


def test_point_in_time_validation_passes_when_future_is_appended():
    base = [100.0 * (1.002 ** i) for i in range(180)]
    future = [1000.0 * (1.05 ** i) for i in range(100)]
    result = PointInTimeValidationService.validate_all(candles_from_closes(base), future_candles=candles_from_closes(future))
    assert result.passed is True
    assert set(result.checked_layers) == {"forecast", "model_selection", "walk_forward"}
    assert result.failures == ()


def test_forecast_validation_detects_changed_origin_input():
    base = candles_from_closes([100.0 * (1.001 ** i) for i in range(180)])
    changed = list(base)
    changed[-1] = Candle(
        changed[-1].timestamp,
        999.0,
        1000.0,
        998.0,
        999.0,
        changed[-1].volume,
    )
    assert PointInTimeValidationService.validate_forecast(base, future_candles=()) is True
    assert PointInTimeValidationService.validate_forecast(base, future_candles=changed[-20:]) is False


def test_validation_reports_layer_failure():
    base = candles_from_closes([100.0 * (1.001 ** i) for i in range(120)])
    future = candles_from_closes([2000.0 * (1.05 ** i) for i in range(100)])
    result = PointInTimeValidationService.validate_all(base, future_candles=future)
    assert isinstance(result.passed, bool)
    assert all(isinstance(item, str) for item in result.failures)
