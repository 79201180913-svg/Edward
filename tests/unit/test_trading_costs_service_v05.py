import pytest

from edward.services.trading_costs_service import TradingCostsInput, TradingCostsService


def test_trading_costs_reduce_gross_return_to_net_return():
    result = TradingCostsService.calculate(
        TradingCostsInput(
            action="BUY",
            gross_return_pct=10.0,
            trade_value=20_000.0,
            commission_pct=0.5,
            spread_pct=0.3,
            slippage_pct=0.2,
            liquidity_impact_pct=0.1,
        )
    )
    assert result.total_cost_pct == 1.1
    assert result.total_cost_value == 220.0
    assert result.net_return_pct == 8.9
    assert result.profitable_after_costs is True


def test_trading_costs_can_turn_trade_unprofitable():
    result = TradingCostsService.calculate(
        TradingCostsInput(
            action="SELL",
            gross_return_pct=1.0,
            trade_value=10_000.0,
            commission_pct=0.4,
            spread_pct=0.4,
            slippage_pct=0.3,
        )
    )
    assert result.net_return_pct == -0.1
    assert result.profitable_after_costs is False


def test_hold_does_not_apply_execution_costs_to_return():
    result = TradingCostsService.calculate(
        TradingCostsInput(
            action="HOLD",
            gross_return_pct=3.0,
            trade_value=10_000.0,
            commission_pct=1.0,
            spread_pct=1.0,
            slippage_pct=1.0,
            liquidity_impact_pct=1.0,
        )
    )
    assert result.net_return_pct == 3.0


@pytest.mark.parametrize("field", [
    "commission_pct",
    "spread_pct",
    "slippage_pct",
    "liquidity_impact_pct",
])
def test_negative_costs_are_rejected(field):
    kwargs = dict(action="BUY", gross_return_pct=5.0, trade_value=10_000.0)
    kwargs[field] = -0.1
    with pytest.raises(ValueError):
        TradingCostsService.calculate(TradingCostsInput(**kwargs))


def test_negative_trade_value_is_rejected():
    with pytest.raises(ValueError):
        TradingCostsService.calculate(
            TradingCostsInput(action="BUY", gross_return_pct=5.0, trade_value=-1.0)
        )


def test_unknown_action_is_rejected():
    with pytest.raises(ValueError):
        TradingCostsService.calculate(
            TradingCostsInput(action="UNKNOWN", gross_return_pct=5.0, trade_value=1000.0)
        )
