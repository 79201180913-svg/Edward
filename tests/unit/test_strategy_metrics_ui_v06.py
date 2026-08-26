from edward.ui.strategy_metrics_ui_v06 import build_strategy_metrics_view, strategy_metrics_text


def test_failed_quality_gate_hides_strategy_confidence():
    view = build_strategy_metrics_view(
        strategy_name="Trend Following",
        quality_gate=False,
        strategy_confidence="High",
        forecast_confidence="High",
    )
    assert view.quality_gate == "FAIL"
    assert view.strategy_confidence == "N/A"
    assert view.forecast_confidence == "High"


def test_passed_quality_gate_keeps_strategy_confidence_and_forecast_is_independent():
    view = build_strategy_metrics_view(
        strategy_name="Trend Following",
        quality_gate=True,
        strategy_confidence="Medium",
        forecast_confidence="Low",
    )
    assert view.quality_gate == "PASS"
    assert view.strategy_confidence == "Medium"
    assert view.forecast_confidence == "Low"


def test_strategy_metrics_text_labels_metrics_separately():
    view = build_strategy_metrics_view(
        strategy_name="Momentum",
        quality_gate=False,
        strategy_confidence="High",
        forecast_confidence="High",
    )
    text = strategy_metrics_text(view)
    assert "Качество стратегии: FAIL" in text
    assert "Уверенность стратегии: N/A" in text
    assert "Уверенность прогноза: High" in text
