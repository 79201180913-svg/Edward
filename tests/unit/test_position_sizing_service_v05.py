import pytest

from edward.services.position_sizing_service import PositionSizingInput, PositionSizingService


def base_input(**overrides):
    data = dict(
        action="BUY",
        portfolio_value=100_000.0,
        current_price=100.0,
        stop_price=95.0,
        risk_per_trade_pct=1.0,
        max_position_weight_pct=10.0,
        available_cash=50_000.0,
        current_quantity=0,
        current_weight_pct=0.0,
        lot_size=1,
    )
    data.update(overrides)
    return PositionSizingInput(**data)


def test_position_sizing_returns_quantity_value_weight_and_risk():
    result = PositionSizingService.calculate(base_input())
    assert result.recommended_quantity == 100
    assert result.recommended_value == 10_000.0
    assert result.recommended_weight_pct == 10.0
    assert result.risk_pct == 0.5


def test_position_sizing_is_capped_by_max_position():
    result = PositionSizingService.calculate(base_input(max_position_weight_pct=5.0))
    assert result.recommended_quantity == 50
    assert result.capped_by_max_position is True


def test_position_sizing_is_capped_by_cash():
    result = PositionSizingService.calculate(base_input(available_cash=3_000.0))
    assert result.recommended_quantity == 30
    assert result.capped_by_cash is True


def test_position_sizing_respects_lot_size():
    result = PositionSizingService.calculate(base_input(lot_size=10))
    assert result.recommended_quantity % 10 == 0


def test_hold_returns_zero_new_quantity():
    result = PositionSizingService.calculate(base_input(action="HOLD"))
    assert result.recommended_quantity == 0
    assert result.reduction_quantity == 0


def test_sell_reduces_entire_current_quantity():
    result = PositionSizingService.calculate(base_input(action="SELL", current_quantity=73, lot_size=10))
    assert result.recommended_quantity == 70
    assert result.reduction_quantity == 70


def test_reduce_returns_partial_reduction():
    result = PositionSizingService.calculate(base_input(action="REDUCE", current_quantity=100, lot_size=10))
    assert result.reduction_quantity == 50


@pytest.mark.parametrize(
    "kwargs",
    [
        {"portfolio_value": 0},
        {"current_price": 0},
        {"risk_per_trade_pct": -1},
        {"max_position_weight_pct": -1},
        {"available_cash": -1},
        {"lot_size": 0},
    ],
)
def test_invalid_position_sizing_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        PositionSizingService.calculate(base_input(**kwargs))
