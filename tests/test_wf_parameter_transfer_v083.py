from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_transfer_service_v083 import WFParameterTransferSelectorV083


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


def test_selector_prefers_multi_criterion_consensus_over_excess_return_only_winner():
    candidates = [
        ({"lookback": 10}, result({"lookback": 10}, excess=10.0, sharpe=-1.0, sortino=-1.0, return_pct=2.0, drawdown=2.0)),
        ({"lookback": 20}, result({"lookback": 20}, excess=9.0, sharpe=2.0, sortino=2.0, return_pct=9.0, drawdown=3.0)),
        ({"lookback": 30}, result({"lookback": 30}, excess=8.0, sharpe=1.0, sortino=1.0, return_pct=6.0, drawdown=3.0)),
    ]

    selection = WFParameterTransferSelectorV083.select(candidates)

    assert selection.baseline_parameters == {"lookback": 10}
    assert selection.selected_parameters == {"lookback": 20}
    assert selection.changed_from_baseline is True
    assert selection.selected_score > selection.baseline_score


def test_selector_is_deterministic_and_ranks_candidates_by_selection_score():
    candidates = [
        ({"lookback": 10}, result({"lookback": 10}, excess=10.0, sharpe=-1.0, sortino=-1.0, return_pct=2.0, drawdown=2.0)),
        ({"lookback": 20}, result({"lookback": 20}, excess=9.0, sharpe=2.0, sortino=2.0, return_pct=9.0, drawdown=3.0)),
        ({"lookback": 30}, result({"lookback": 30}, excess=8.0, sharpe=1.0, sortino=1.0, return_pct=6.0, drawdown=3.0)),
    ]

    first = WFParameterTransferSelectorV083.select(candidates)
    second = WFParameterTransferSelectorV083.select(candidates)

    assert first.selected_parameters == second.selected_parameters
    assert first.candidates == second.candidates
    assert first.candidates[0].selection_score >= first.candidates[1].selection_score
    assert first.candidates[1].selection_score >= first.candidates[2].selection_score


def test_selector_never_requires_oos_data():
    assert "oos" not in WFParameterTransferSelectorV083.select.__code__.co_varnames
