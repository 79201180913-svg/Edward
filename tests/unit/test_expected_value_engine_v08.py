from __future__ import annotations

from edward.services.expected_value_engine_v08 import ExpectedValueEngine
from edward.services.research_backtest_service_v08 import BacktestTrade


def _trade(value: float, cost: float = 0.0) -> BacktestTrade:
    return BacktestTrade(None, None, 100.0, 100.0, value + cost, cost, value)


def test_expected_value_uses_after_cost_trade_outcomes():
    result = ExpectedValueEngine.from_trades((_trade(10.0), _trade(5.0), _trade(-4.0), _trade(-6.0)))

    assert result.probability_profit_pct == 50.0
    assert result.probability_loss_pct == 50.0
    assert result.average_win_pct == 7.5
    assert result.average_loss_pct == 5.0
    assert result.expected_value_pct == 1.25


def test_uncertainty_distribution_is_reported():
    result = ExpectedValueEngine.from_returns([-10.0, -5.0, 0.0, 5.0, 10.0])

    assert result.observations == 5
    assert result.p10_pct < result.median_pct < result.p90_pct
    assert result.uncertainty_width_pct == result.p90_pct - result.p10_pct
    assert result.confidence == "Low"


def test_confidence_depends_on_observation_count_not_return_sign():
    result = ExpectedValueEngine.from_returns([1.0] * 30)
    assert result.confidence == "Medium"
    assert result.expected_value_pct == 1.0
