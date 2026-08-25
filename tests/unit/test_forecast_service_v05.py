from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.forecast_service import ForecastService


def candles_from_closes(closes: list[float]) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(days=index),
            open=value,
            high=value * 1.01,
            low=value * 0.99,
            close=value,
            volume=1000,
        )
        for index, value in enumerate(closes)
    ]


def test_forecast_returns_all_supported_horizons_and_probability_bounds():
    closes = [100.0 * (1.003**index) for index in range(180)]
    result = ForecastService.forecast(
        instrument_uid="uid-1",
        ticker="TEST",
        candles=candles_from_closes(closes),
    )

    assert [point.horizon_days for point in result.points] == [1, 5, 20, 60]
    assert result.model == "AdaptiveHistoricalDrift"
    for point in result.points:
        assert 0.0 <= point.probability_up <= 100.0
        assert 0.0 <= point.probability_down <= 100.0
        assert point.probability_up + point.probability_down == pytest.approx(100.0)
        assert point.downside_price <= point.expected_price <= point.upside_price


def test_positive_drift_produces_positive_expected_return():
    closes = [100.0 * (1.005**index) for index in range(200)]
    result = ForecastService.forecast(
        instrument_uid="uid-2",
        ticker="UP",
        candles=candles_from_closes(closes),
    )

    point = result.point(20)
    assert point.expected_return_pct > 0
    assert point.probability_up > 50
    assert point.upside_price > point.current_price


def test_negative_drift_produces_negative_expected_return():
    closes = [200.0 * (0.995**index) for index in range(200)]
    result = ForecastService.forecast(
        instrument_uid="uid-3",
        ticker="DOWN",
        candles=candles_from_closes(closes),
    )

    point = result.point(20)
    assert point.expected_return_pct < 0
    assert point.probability_down > 50
    assert point.downside_price < point.current_price


def test_forecast_is_point_in_time_and_ignores_future_candles_after_origin():
    base = [100.0 * (1.002**index) for index in range(180)]
    future = [1000.0 * (1.05**index) for index in range(20)]
    origin = candles_from_closes(base)
    with_future = candles_from_closes(base + future)

    first = ForecastService.forecast(
        instrument_uid="uid-4",
        ticker="TEST",
        candles=origin,
    )
    second = ForecastService.forecast(
        instrument_uid="uid-4",
        ticker="TEST",
        candles=with_future,
    )

    first_point = first.point(5)
    second_origin_price = second.point(5).current_price
    assert first_point.current_price != second_origin_price
    assert first_point.current_price == origin[-1].close


def test_forecast_requires_enough_history():
    with pytest.raises(ValueError, match="не менее 60"):
        ForecastService.forecast(
            instrument_uid="uid-5",
            ticker="SHORT",
            candles=candles_from_closes([100.0] * 59),
        )


def test_forecast_rejects_unsupported_horizon():
    with pytest.raises(ValueError, match="Неподдерживаемые горизонты"):
        ForecastService.forecast(
            instrument_uid="uid-6",
            ticker="TEST",
            candles=candles_from_closes([100.0 * (1.001**index) for index in range(100)]),
            horizons=[7],
        )
