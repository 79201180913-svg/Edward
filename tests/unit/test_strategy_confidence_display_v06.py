from types import SimpleNamespace

from edward.ui.strategy_confidence_display_v06 import (
    confidence_detail,
    forecast_confidence_label,
    opportunity_strategy_confidence,
    strategy_confidence_label,
    strategy_quality_label,
)


def test_strategy_quality_and_confidence_labels():
    assert strategy_quality_label(True) == "PASS"
    assert strategy_quality_label(False) == "FAIL"
    assert strategy_quality_label(None) == "N/A"
    assert strategy_confidence_label("High") == "High"
    assert strategy_confidence_label("unexpected") == "N/A"
    assert forecast_confidence_label("Medium") == "Medium"


def test_opportunity_failed_strategy_reports_na_confidence():
    result = SimpleNamespace(reason="STRATEGY_QUALITY_FAIL", strategy_confidence=None)
    assert opportunity_strategy_confidence(result) == "N/A"


def test_confidence_detail_separates_strategy_and_forecast():
    assert confidence_detail(
        quality_gate=False,
        strategy_confidence="N/A",
        forecast_confidence="High",
    ) == "Качество стратегии: FAIL\nУверенность стратегии: N/A\nУверенность прогноза: High"
