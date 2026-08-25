from types import SimpleNamespace

from edward.ui.opportunity_search_ui_v04 import _forecast_probability, _forecast_value, _trade_plan_text


def test_forecast_value_formats_selected_horizon():
    points = ((1, 101.23456), (5, 105.67891), (20, 120.0))
    assert _forecast_value(points, 5) == "105.6789"
    assert _forecast_value(points, 60) == "—"


def test_forecast_probability_formats_selected_horizon():
    points = ((1, 51.234), (5, 67.89))
    assert _forecast_probability(points, 5) == "67.9%"
    assert _forecast_probability(points, 20) == "—"


def test_trade_plan_text_contains_execution_fields():
    plan = SimpleNamespace(
        entry_low=100.0,
        entry_high=102.0,
        target_price=115.0,
        stop_price=96.0,
        expected_return_pct=15.0,
        expected_risk_pct=4.0,
        risk_reward=3.75,
        holding_horizon_days=20,
        confidence="High",
    )
    item = SimpleNamespace(trade_plan=plan, recommended_quantity=50, recommended_weight_pct=6.5, execution_ready=True)
    text = _trade_plan_text(item)
    assert "Вход: 100.0000 — 102.0000" in text
    assert "Цель: 115.0000" in text
    assert "Стоп: 96.0000" in text
    assert "Risk/Reward: 3.75" in text
    assert "Execution Ready: ДА" in text
