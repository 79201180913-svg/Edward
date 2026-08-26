from datetime import datetime, timezone

import pytest

from edward.services.forecast_service import ForecastPoint
from edward.services.trade_plan_service import TradePlanInput, TradePlanService


def point(*, current=100.0, expected=108.0, downside=95.0, upside=112.0, confidence="High"):
    return ForecastPoint(
        horizon_days=20,
        current_price=current,
        expected_price=expected,
        expected_return_pct=8.0,
        downside_price=downside,
        upside_price=upside,
        probability_up=68.0,
        probability_down=32.0,
        expected_volatility_pct=9.0,
        expected_drawdown_pct=5.0,
        confidence=confidence,
    )


def test_build_buy_plan_has_entry_target_stop_and_risk_reward():
    result = TradePlanService.build(
        TradePlanInput(action="BUY", forecast=point(), confidence="High", holding_horizon_days=20)
    )

    assert result.action == "BUY"
    assert result.entry_low < result.entry_high
    assert result.target_price >= 108.0
    assert result.stop_price < 100.0
    assert result.expected_return_pct > 0
    assert result.expected_risk_pct > 0
    assert result.risk_reward is not None


def test_build_add_plan_respects_explicit_entry():
    result = TradePlanService.build(
        TradePlanInput(
            action="ADD",
            forecast=point(),
            confidence="Medium",
            holding_horizon_days=5,
            entry_price=101.0,
        )
    )

    assert result.entry_low < 101.0 < result.entry_high
    assert result.target_price is not None


def test_build_sell_and_reduce_use_exit_style_plan():
    for action in ("REDUCE", "SELL"):
        result = TradePlanService.build(
            TradePlanInput(action=action, forecast=point(), confidence="High", holding_horizon_days=20)
        )
        assert result.action == action
        assert result.entry_low == result.entry_high
        assert result.target_price == 95.0
        assert result.stop_price == 112.0


def test_build_hold_uses_current_price_as_entry():
    result = TradePlanService.build(
        TradePlanInput(action="HOLD", forecast=point(), confidence="Medium", holding_horizon_days=1)
    )

    assert result.entry_low == 100.0
    assert result.entry_high == 100.0
    assert result.target_price == 108.0
    assert result.stop_price == 95.0


def test_rejects_invalid_action_price_and_horizon():
    with pytest.raises(ValueError):
        TradePlanService.build(TradePlanInput(action="WAIT", forecast=point(), confidence="High", holding_horizon_days=5))

    with pytest.raises(ValueError):
        TradePlanService.build(TradePlanInput(action="BUY", forecast=point(current=0.0), confidence="High", holding_horizon_days=5))

    with pytest.raises(ValueError):
        TradePlanService.build(TradePlanInput(action="BUY", forecast=point(), confidence="High", holding_horizon_days=0))
