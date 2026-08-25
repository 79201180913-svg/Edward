from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.forecast_walk_forward_service import ForecastWalkForwardService


def candles_from_closes(closes: list[float]) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            start + timedelta(days=index),
            value,
            value * 1.01,
            value * 0.99,
            value,
            1000 + index,
        )
        for index, value in enumerate(closes)
    ]


def test_walk_forward_returns_out_of_sample_metrics_and_selected_model():
    closes = [100.0 * (1.002 ** index) for index in range(220)]
    result = ForecastWalkForwardService.validate(
        candles=candles_from_closes(closes),
        horizon=5,
    )

    assert result.horizon_days == 5
    assert result.selected_model
    assert len(result.windows) >= 7
    assert result.mean_mae_pct >= 0
    assert result.mean_rmse_pct >= 0
    assert 0 <= result.mean_directional_accuracy_pct <= 100
    assert 0 <= result.mean_hit_rate_pct <= 100
    assert 0 <= result.stability_pct <= 100
    assert 0 <= result.quality_score <= 100
    assert all(window.validation_size == 20 for window in result.windows)


def test_walk_forward_does_not_use_future_validation_after_window_origin():
    base = [100.0 * (1.002 ** index) for index in range(180)]
    future = [1000.0 * (1.05 ** index) for index in range(100)]

    first = ForecastWalkForwardService.validate(
        candles=candles_from_closes(base),
        horizon=5,
    )
    second = ForecastWalkForwardService.validate(
        candles=candles_from_closes(base + future),
        horizon=5,
    )

    # The earliest walk-forward windows have exactly the same training prefix;
    # adding later candles must not alter their out-of-sample metrics.
    assert first.windows[0] == second.windows[0]


def test_walk_forward_validates_supported_horizons_below_validation_window():
    closes = [100.0 * (1.0015 ** index) for index in range(240)]
    results = ForecastWalkForwardService.validate_all(
        candles=candles_from_closes(closes),
        horizons=(1, 5, 19),
    )

    assert [item.horizon_days for item in results] == [1, 5, 19]
    assert all(item.selected_model for item in results)


def test_walk_forward_rejects_invalid_history_and_horizon():
    closes = [100.0 * (1.001 ** index) for index in range(70)]
    candles = candles_from_closes(closes)

    with pytest.raises(ValueError, match="Недостаточно истории"):
        ForecastWalkForwardService.validate(candles=candles, horizon=5)

    with pytest.raises(ValueError, match="меньше размера validation окна"):
        ForecastWalkForwardService.validate(candles=candles_from_closes(closes + closes), horizon=20)
