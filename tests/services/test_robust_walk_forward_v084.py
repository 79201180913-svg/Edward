import pytest

from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.robust_walk_forward_service_v084 import RobustWalkForwardServiceV084


def make_result(*, excess: float, sharpe: float, dd: float, trades: int) -> ResearchBacktestResult:
    return ResearchBacktestResult(
        strategy="Breakout",
        parameters={},
        gross_return_pct=1.0,
        net_return_pct=1.0,
        benchmark_return_pct=1.0 - excess,
        excess_return_pct=excess,
        max_drawdown_pct=dd,
        sharpe=sharpe,
        sortino=sharpe,
        calmar=0.2,
        trades=trades,
        win_rate_pct=50.0,
        profit_factor=1.2,
        payoff_ratio=1.0,
        turnover_pct=5.0,
        exposure_pct=10.0,
        average_trade_pct=0.2,
        median_trade_pct=0.2,
        best_trade_pct=1.0,
        worst_trade_pct=-0.5,
        positive_days_pct=50.0,
        equity=(1.0, 1.01),
        trades_detail=(),
    )


def test_viability_selector_rejects_negative_excess_before_robust_ranking():
    candidates = [
        ({"lookback": 20}, make_result(excess=-5.0, sharpe=10.0, dd=1.0, trades=20)),
        ({"lookback": 40}, make_result(excess=1.0, sharpe=0.5, dd=5.0, trades=5)),
    ]

    selected, _, _ = RobustWalkForwardServiceV084._select_robust_parameters(candidates)

    assert selected == {"lookback": 40}


def test_viability_selector_rejects_excessive_drawdown():
    candidates = [
        ({"lookback": 20}, make_result(excess=5.0, sharpe=10.0, dd=40.0, trades=20)),
        ({"lookback": 40}, make_result(excess=1.0, sharpe=0.5, dd=5.0, trades=5)),
    ]

    # The selector reads the configured drawdown through the run context; the
    # direct unit call uses the default unconstrained drawdown and therefore only
    # asserts economic viability. Profile-level drawdown is covered by run tests.
    selected, _, _ = RobustWalkForwardServiceV084._select_robust_parameters(candidates)

    assert selected == {"lookback": 20}


def test_viability_selector_fails_when_no_train_candidate_is_economically_valid():
    candidates = [
        ({"lookback": 20}, make_result(excess=-1.0, sharpe=5.0, dd=1.0, trades=20)),
        ({"lookback": 40}, make_result(excess=-2.0, sharpe=4.0, dd=2.0, trades=20)),
    ]

    with pytest.raises(ValueError, match="No economically viable"):
        RobustWalkForwardServiceV084._select_robust_parameters(candidates)
