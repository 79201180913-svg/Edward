from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.forecast_model_selection_service import ForecastModelSelectionService


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


def test_selector_returns_selection_for_each_requested_horizon():
    closes = [100.0 * (1.002 ** index) for index in range(140)]
    result = ForecastModelSelectionService.select_and_forecast(
        instrument_uid="uid-1",
        ticker="TEST",
        candles=candles_from_closes(closes),
        horizons=(1, 5, 20),
    )

    assert result.forecast.model == "AdaptiveModelSelection"
    assert [point.horizon_days for point in result.forecast.points] == [1, 5, 20]
    assert [item.horizon_days for item in result.selections] == [1, 5, 20]
    assert all(item.selected_model in ForecastModelSelectionService.MODELS for item in result.selections)
    assert all(0 <= item.score <= 100 for item in result.selections)


def test_selector_exposes_all_candidate_models_and_metrics():
    closes = [100.0 * (1.0015 ** index) for index in range(150)]
    result = ForecastModelSelectionService.select_and_forecast(
        instrument_uid="uid-2",
        ticker="TEST",
        candles=candles_from_closes(closes),
        horizons=(5,),
    )

    selection = result.selections[0]
    assert {item.name for item in selection.candidates} == set(ForecastModelSelectionService.MODELS)
    assert all(item.absolute_error_pct >= 0 for item in selection.candidates)
    assert all(0 <= item.directional_accuracy_pct <= 100 for item in selection.candidates)


def test_selector_is_point_in_time_safe():
    base = [100.0 * (1.001 ** index) for index in range(150)]
    future = [1000.0 * (1.05 ** index) for index in range(30)]

    first = ForecastModelSelectionService.select_and_forecast(
        instrument_uid="uid-3",
        ticker="TEST",
        candles=candles_from_closes(base),
        horizons=(5,),
    )
    second = ForecastModelSelectionService.select_and_forecast(
        instrument_uid="uid-3",
        ticker="TEST",
        candles=candles_from_closes(base + future),
        horizons=(5,),
    )

    # The model is allowed to change when new information is available, but
    # the first run must be based only on its own final candle.
    assert first.forecast.point(5).current_price == base[-1]
    assert second.forecast.point(5).current_price == (base + future)[-1]


def test_selector_rejects_insufficient_history():
    closes = [100.0 * (1.001 ** index) for index in range(80)]
    try:
        ForecastModelSelectionService.select_and_forecast(
            instrument_uid="uid-4",
            ticker="TEST",
            candles=candles_from_closes(closes),
            horizons=(5,),
        )
    except ValueError as exc:
        assert "модели" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for insufficient history")
