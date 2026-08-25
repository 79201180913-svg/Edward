from dataclasses import replace

from edward.services.forecast_quality_gate_service import ForecastQualityGateService
from edward.services.forecast_walk_forward_service import ForecastWalkForwardResult, ForecastWindowMetrics


def _result(*, quality=75.0, direction=62.0, stability=70.0, windows=4):
    window = ForecastWindowMetrics(
        model="HistoricalDrift",
        horizon_days=5,
        train_size=60,
        validation_size=20,
        mae_pct=1.0,
        rmse_pct=1.2,
        directional_accuracy_pct=direction,
        hit_rate_pct=direction,
        score=quality,
    )
    return ForecastWalkForwardResult(
        horizon_days=5,
        selected_model="HistoricalDrift",
        windows=tuple(window for _ in range(windows)),
        mean_mae_pct=1.0,
        mean_rmse_pct=1.2,
        mean_directional_accuracy_pct=direction,
        mean_hit_rate_pct=direction,
        stability_pct=stability,
        quality_score=quality,
    )


def test_quality_gate_passes_good_forecast():
    result = ForecastQualityGateService.evaluate(_result())

    assert result.passed is True
    assert result.reasons == ()
    assert result.windows_count == 4


def test_quality_gate_fails_low_quality_score():
    result = ForecastQualityGateService.evaluate(_result(quality=59.9))

    assert result.passed is False
    assert any("Качество прогноза" in reason for reason in result.reasons)


def test_quality_gate_fails_low_directional_accuracy():
    result = ForecastQualityGateService.evaluate(_result(direction=54.9))

    assert result.passed is False
    assert any("Directional Accuracy" in reason for reason in result.reasons)


def test_quality_gate_fails_low_stability():
    result = ForecastQualityGateService.evaluate(_result(stability=49.9))

    assert result.passed is False
    assert any("Стабильность" in reason for reason in result.reasons)


def test_quality_gate_fails_insufficient_windows():
    result = ForecastQualityGateService.evaluate(_result(windows=2))

    assert result.passed is False
    assert any("Недостаточно OOS-окон" in reason for reason in result.reasons)


def test_quality_gate_reports_all_failed_conditions():
    result = ForecastQualityGateService.evaluate(
        _result(quality=20.0, direction=20.0, stability=10.0, windows=1)
    )

    assert result.passed is False
    assert len(result.reasons) == 4


def test_quality_gate_supports_custom_thresholds():
    result = ForecastQualityGateService.evaluate(
        _result(quality=40.0, direction=45.0, stability=35.0, windows=2),
        min_quality_score=40.0,
        min_directional_accuracy_pct=45.0,
        min_stability_pct=35.0,
        min_windows=2,
    )

    assert result.passed is True


def test_quality_gate_evaluate_all():
    results = ForecastQualityGateService.evaluate_all([_result(), _result(quality=50.0)])

    assert len(results) == 2
    assert results[0].passed is True
    assert results[1].passed is False
