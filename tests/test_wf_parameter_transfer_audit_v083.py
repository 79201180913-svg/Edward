from dataclasses import dataclass
from datetime import datetime, timedelta

from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_transfer_audit_service_v083 import WFParameterTransferAuditServiceV083
from edward.services.wf_parameter_transfer_service_v083 import ParameterTransferHistoryEntry, WFParameterTransferSelectorV083


def _result(params, value, trades=1):
    return ResearchBacktestResult(
        strategy="Test", parameters=dict(params), gross_return_pct=value, net_return_pct=value,
        benchmark_return_pct=0.0, excess_return_pct=value, max_drawdown_pct=1.0,
        sharpe=value, sortino=value, calmar=value, trades=trades, win_rate_pct=100.0,
        profit_factor=2.0, payoff_ratio=2.0, turnover_pct=1.0, exposure_pct=10.0,
        average_trade_pct=value, median_trade_pct=value, best_trade_pct=value,
        worst_trade_pct=value, positive_days_pct=100.0, equity=(1.0, 1.0 + value / 100.0),
        trades_detail=(),
    )


def test_history_is_all_prior_candidate_oos_not_only_baseline():
    history = [
        ParameterTransferHistoryEntry(0, {"p": 1}, 1.0, 1.0, 1.0),
        ParameterTransferHistoryEntry(0, {"p": 2}, 9.0, 2.0, 1.0),
        ParameterTransferHistoryEntry(0, {"p": 3}, -1.0, -1.0, 2.0),
    ]
    candidates = [
        ({"p": 1}, _result({"p": 1}, 3.0)),
        ({"p": 2}, _result({"p": 2}, 2.0)),
        ({"p": 3}, _result({"p": 3}, 1.0)),
    ]
    selection = WFParameterTransferSelectorV083.select_with_history(candidates, history=history, baseline_parameters={"p": 1})
    rows = {tuple(row.parameters.items()): row for row in selection.candidates}
    assert rows[(("p", 2),)].historical_support == 1
    assert rows[(("p", 3),)].historical_support == 1


def test_selector_has_no_current_oos_argument():
    assert "oos_candidates" not in WFParameterTransferSelectorV083.select_with_history.__code__.co_varnames


def test_activity_classification_does_not_treat_inactive_as_negative():
    assert WFParameterTransferAuditServiceV083._activity(_result({"p": 1}, -5.0, trades=0)) == "INACTIVE"
    assert WFParameterTransferAuditServiceV083._activity(_result({"p": 1}, 5.0, trades=1)) == "ACTIVE_POSITIVE"
    assert WFParameterTransferAuditServiceV083._activity(_result({"p": 1}, -5.0, trades=1)) == "ACTIVE_NEGATIVE"


def test_audit_exposes_oos_oracle_separately_from_train_baseline(monkeypatch):
    @dataclass(frozen=True)
    class CandleStub:
        timestamp: datetime
        open: float
        high: float
        low: float
        close: float
        volume: float

    candles = [
        CandleStub(
            timestamp=datetime(2026, 1, 1) + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
            volume=1000.0,
        )
        for i in range(4)
    ]

    def fake_run(*, candles, strategy, parameters, signal_fn, costs=None):
        # Train (days 1-2): p=1 is the baseline winner.
        # OOS (days 3-4): p=2 is the oracle winner and p=1 loses.
        if candles[0].timestamp.day == 1:
            value = 3.0 if parameters["p"] == 1 else 1.0
        else:
            value = -1.0 if parameters["p"] == 1 else 3.0
        return _result(parameters, value)

    monkeypatch.setattr("edward.services.wf_parameter_transfer_audit_service_v083.ResearchBacktestService.run", fake_run)

    def factory(strategy, params):
        return lambda candles, index: False

    result = WFParameterTransferAuditServiceV083.run(
        candles=candles,
        strategy="Test",
        parameter_grid=[{"p": 1}, {"p": 2}],
        signal_factory=factory,
        train_size=2,
        test_size=2,
    )

    assert len(result.windows) == 1
    window = result.windows[0]
    assert window.baseline_parameters == {"p": 1}
    assert window.oracle_parameters == {"p": 2}
    assert window.baseline_oos_return_pct == -1.0
    assert window.oracle_oos_return_pct == 3.0
    assert window.oracle_delta_return_pct == 4.0
    assert result.baseline_mean_oos_return_pct == -1.0
    assert result.oracle_mean_oos_return_pct == 3.0
    assert result.oracle_mean_delta_pct == 4.0


def test_audit_window_zero_has_empty_history_and_later_window_has_prior_entries():
    @dataclass(frozen=True)
    class CandleStub:
        timestamp: datetime
        open: float
        high: float
        low: float
        close: float
        volume: float

    candles = [
        CandleStub(
            timestamp=datetime(2026, 1, 1) + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
            volume=1000.0,
        )
        for i in range(8)
    ]

    def factory(strategy, params):
        def signal(candles, index):
            return False
        return signal

    result = WFParameterTransferAuditServiceV083.run(
        candles=candles,
        strategy="Test",
        parameter_grid=[{"p": 1}, {"p": 2}],
        signal_factory=factory,
        train_size=2,
        test_size=2,
    )
    assert result.windows
    assert result.windows[0].history_entries_before_window == 0
    if len(result.windows) > 1:
        assert result.windows[1].history_entries_before_window == 2
    assert result.baseline_inactive_windows == len(result.windows)
