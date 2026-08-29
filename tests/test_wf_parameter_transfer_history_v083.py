from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_transfer_service_v083 import (
    ParameterTransferHistoryEntry,
    WFParameterTransferSelectorV083,
)


def result(parameters, *, excess, sharpe, sortino, return_pct, drawdown):
    return ResearchBacktestResult(
        strategy="Test",
        parameters=dict(parameters),
        gross_return_pct=return_pct,
        net_return_pct=return_pct,
        benchmark_return_pct=0.0,
        excess_return_pct=excess,
        max_drawdown_pct=drawdown,
        sharpe=sharpe,
        sortino=sortino,
        calmar=return_pct / max(drawdown, 1e-9),
        trades=5,
        win_rate_pct=60.0,
        profit_factor=1.5,
        payoff_ratio=1.2,
        turnover_pct=10.0,
        exposure_pct=20.0,
        average_trade_pct=1.0,
        median_trade_pct=1.0,
        best_trade_pct=3.0,
        worst_trade_pct=-2.0,
        positive_days_pct=55.0,
        equity=(1.0, 1.01),
        trades_detail=(),
    )


def test_history_is_used_only_after_minimum_support_is_reached():
    candidates = [
        ({"lookback": 10}, result({"lookback": 10}, excess=9.0, sharpe=1.0, sortino=1.0, return_pct=5.0, drawdown=3.0)),
        ({"lookback": 20}, result({"lookback": 20}, excess=8.5, sharpe=1.2, sortino=1.2, return_pct=5.5, drawdown=3.0)),
    ]
    history = [
        ParameterTransferHistoryEntry(0, {"lookback": 20}, 8.0, 1.8, 2.0, 90.0),
        ParameterTransferHistoryEntry(1, {"lookback": 20}, 7.0, 1.6, 2.5, 85.0),
    ]

    selection = WFParameterTransferSelectorV083.select_with_history(
        candidates,
        history=history,
        baseline_parameters={"lookback": 10},
    )

    row = next(item for item in selection.candidates if item.parameters == {"lookback": 20})
    assert row.historical_support == 2
    assert row.historical_score > 0.0


def test_single_historical_observation_does_not_override_current_train_selection():
    candidates = [
        ({"lookback": 10}, result({"lookback": 10}, excess=10.0, sharpe=2.0, sortino=2.0, return_pct=9.0, drawdown=2.0)),
        ({"lookback": 20}, result({"lookback": 20}, excess=7.0, sharpe=0.5, sortino=0.5, return_pct=3.0, drawdown=5.0)),
    ]
    history = [
        ParameterTransferHistoryEntry(0, {"lookback": 20}, 100.0, 10.0, 0.1, 100.0),
    ]

    selection = WFParameterTransferSelectorV083.select_with_history(candidates, history=history)

    assert selection.selected_parameters == {"lookback": 10}


def test_current_oos_values_are_not_part_of_history_selector_api():
    assert "oos" not in WFParameterTransferSelectorV083.select_with_history.__code__.co_varnames
    assert "oos" not in WFParameterTransferSelectorV083._select.__code__.co_varnames
