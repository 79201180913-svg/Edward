from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_transfer_shadow_service_v083 import WFParameterTransferShadowServiceV083


def _result(parameters, *, excess, sharpe, return_pct, drawdown):
    return ResearchBacktestResult(
        strategy="Test",
        parameters=dict(parameters),
        gross_return_pct=return_pct,
        net_return_pct=return_pct,
        benchmark_return_pct=0.0,
        excess_return_pct=excess,
        max_drawdown_pct=drawdown,
        sharpe=sharpe,
        sortino=sharpe,
        calmar=return_pct / max(drawdown, 1e-9),
        trades=3,
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


def test_shadow_comparison_evaluates_baseline_and_shadow_on_same_oos(monkeypatch):
    calls = []

    def fake_run(*, candles, strategy, parameters, signal_fn, costs):
        calls.append((len(candles), dict(parameters)))
        is_train = len(candles) == 4
        if parameters["lookback"] == 10:
            return _result(parameters, excess=10.0 if is_train else 1.0, sharpe=-1.0 if is_train else 0.2, return_pct=2.0 if is_train else 1.0, drawdown=2.0)
        return _result(parameters, excess=9.0 if is_train else 2.0, sharpe=2.0 if is_train else 1.0, return_pct=9.0 if is_train else 2.0, drawdown=3.0)

    monkeypatch.setattr(
        "edward.services.wf_parameter_transfer_shadow_service_v083.ResearchBacktestService.run",
        fake_run,
    )

    candles = [SimpleNamespace(timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)) for i in range(6)]
    result = WFParameterTransferShadowServiceV083.run(
        candles=candles,
        strategy="Test",
        parameter_grid=({"lookback": 10}, {"lookback": 20}),
        signal_factory=lambda strategy, params: lambda sequence, index: True,
        train_size=4,
        test_size=2,
    )

    assert len(result.windows) == 1
    assert result.windows[0].baseline_parameters == {"lookback": 10}
    assert result.windows[0].shadow_parameters == {"lookback": 20}
    assert result.windows[0].baseline_oos_return_pct == 1.0
    assert result.windows[0].shadow_oos_return_pct == 2.0
    assert result.shadow_improved_return_windows == 1
    assert result.shadow_changed_windows == 1
    assert len(calls) == 4
