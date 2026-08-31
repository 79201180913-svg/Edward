import pytest

from edward.services.economic_validation_v088 import EconomicValidationV088, TradingCostModelV088


def test_round_trip_cost_is_two_sides_of_commission_and_slippage():
    model = TradingCostModelV088(commission_pct_per_side=0.1, slippage_pct_per_side=0.05)
    assert model.round_trip_cost_pct == pytest.approx(0.3)


def test_net_return_is_gross_less_round_trip_cost_per_trade():
    model = TradingCostModelV088(commission_pct_per_side=0.1, slippage_pct_per_side=0.05)
    result = EconomicValidationV088.validate((1.0, -0.2, 0.8), model)
    assert result.gross_return_pct == pytest.approx(1.6)
    assert result.total_cost_pct == pytest.approx(0.9)
    assert result.net_return_pct == pytest.approx(0.7)
    assert result.trades == 3


def test_negative_costs_are_rejected():
    with pytest.raises(ValueError):
        TradingCostModelV088(commission_pct_per_side=-0.1)
