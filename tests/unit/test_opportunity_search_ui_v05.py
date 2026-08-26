from types import SimpleNamespace

from edward.ui.opportunity_search_ui_v04 import (
    _display_reason,
    _execution_ready_text,
    _forecast_probability,
    _forecast_value,
    _trade_plan_text,
)


def test_forecast_value_formats_selected_horizon():
    points = ((1, 101.23456), (5, 105.67891), (20, 120.0))
    assert _forecast_value(points, 5) == "105.6789"
    assert _forecast_value(points, 60) == "—"


def test_forecast_probability_formats_selected_horizon():
    points = ((1, 51.234), (5, 67.89))
    assert _forecast_probability(points, 5) == "67.9%"
    assert _forecast_probability(points, 20) == "—"


def test_execution_ready_text_is_localized():
    assert _execution_ready_text(SimpleNamespace(execution_ready=True)) == "Готово"
    assert _execution_ready_text(SimpleNamespace(execution_ready=False)) == "Заблокировано"


def test_display_reason_removes_execution_diagnostics_suffix():
    assert _display_reason("STRATEGY_QUALITY_FAIL | Контроль качества прогноза: FAIL | Исполнение: НЕТ") == "Стратегия не прошла контроль качества"


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
    item = SimpleNamespace(
        trade_plan=plan,
        decision="BUY",
        quantity=0,
        recommended_quantity=50,
        recommended_weight_pct=6.5,
        execution_ready=True,
    )
    text = _trade_plan_text(item)
    assert "Вход: 100.0000 — 102.0000" in text
    assert "Цель: 115.0000" in text
    assert "Стоп: 96.0000" in text
    assert "Risk/Reward: 3.75" in text
    assert "Рекомендуемый размер: 50 шт. / 6.50%" in text
    assert "Исполнение: ДА" in text


def test_trade_plan_text_shows_reduce_quantity_and_remaining_position():
    plan = SimpleNamespace(
        entry_low=0.1,
        entry_high=0.1,
        target_price=0.09,
        stop_price=0.11,
        expected_return_pct=-10.0,
        expected_risk_pct=10.0,
        risk_reward=-1.0,
        holding_horizon_days=20,
        confidence="High",
    )
    item = SimpleNamespace(
        trade_plan=plan,
        decision="REDUCE",
        quantity=2000,
        recommended_quantity=1000,
        recommended_weight_pct=0.5,
        execution_ready=False,
    )
    text = _trade_plan_text(item)
    assert "Объём сокращения: 1000 шт. / останется: 1000 шт." in text
    assert "Исполнение: НЕТ" in text


def test_trade_plan_text_for_pass_does_not_offer_trade():
    item = SimpleNamespace(decision="PASS", trade_plan=None, execution_ready=False)
    assert _trade_plan_text(item) == "Торговый план: не применяется для решения «Пропустить»."
