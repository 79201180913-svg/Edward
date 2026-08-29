from dataclasses import replace

from edward.services.robustness_diagnostics_v083 import RobustnessDiagnosticsServiceV083
from edward.services.robust_walk_forward_service_v08 import (
    ParameterStability,
    RobustWalkForwardResult,
    WalkForwardWindowResult,
)


def _window(index, trades, return_pct, drawdown=5.0, sharpe=0.5, parameters=None):
    return WalkForwardWindowResult(
        index=index,
        train_start=index,
        train_end=index,
        test_start=index,
        test_end=index,
        parameters=parameters or {"p": 1},
        train_score=1.0,
        test_net_return_pct=return_pct,
        test_benchmark_return_pct=0.0,
        test_excess_return_pct=return_pct,
        test_max_drawdown_pct=drawdown,
        test_sharpe=sharpe,
        test_sortino=sharpe,
        test_trades=trades,
    )


def _result(windows):
    positive = sum(item.test_net_return_pct > 0 for item in windows)
    risk_ok = sum(item.test_max_drawdown_pct <= 30 for item in windows)
    sharpe_positive = sum(item.test_sharpe > 0 for item in windows)
    stability = ParameterStability(len(windows), len(windows), 100.0, tuple((tuple(sorted(item.parameters.items())),) for item in windows))
    returns = [item.test_net_return_pct for item in windows]
    return RobustWalkForwardResult(
        strategy="Test",
        windows=tuple(windows),
        mean_test_return_pct=sum(returns) / len(returns),
        median_test_return_pct=0.0,
        std_test_return_pct=0.0,
        worst_test_return_pct=min(returns),
        best_test_return_pct=max(returns),
        mean_test_drawdown_pct=5.0,
        mean_test_sharpe=0.5,
        positive_return_windows=positive,
        risk_ok_windows=risk_ok,
        positive_sharpe_windows=sharpe_positive,
        return_consistency_pct=positive / len(windows) * 100,
        risk_consistency_pct=risk_ok / len(windows) * 100,
        sharpe_consistency_pct=sharpe_positive / len(windows) * 100,
        robustness_score=0.0,
        parameter_stability=stability,
    )


def test_breakdown_reconstructs_existing_robustness_formula():
    result = _result([
        _window(0, 1, 1.0),
        _window(1, 1, 2.0),
        _window(2, 0, -1.0),
        _window(3, 1, -2.0),
    ])

    diagnostics = RobustnessDiagnosticsServiceV083.evaluate(result)

    expected = round(
        diagnostics.return_contribution
        + diagnostics.risk_contribution
        + diagnostics.sharpe_contribution
        + diagnostics.parameter_stability_contribution
        + diagnostics.performance_consistency_contribution,
        2,
    )
    assert diagnostics.robustness_total == expected
    assert diagnostics.return_consistency_score == 50.0
    assert diagnostics.risk_consistency_score == 100.0
    assert diagnostics.sharpe_consistency_score == 50.0
    assert diagnostics.parameter_stability_score == 100.0


def test_activity_diagnostics_separates_all_and_active_windows():
    result = _result([
        _window(0, 1, 1.0),
        _window(1, 1, 2.0),
        _window(2, 0, 0.0),
        _window(3, 0, 0.0),
    ])

    diagnostics = RobustnessDiagnosticsServiceV083.evaluate(result)

    assert diagnostics.total_windows == 4
    assert diagnostics.active_windows == 2
    assert diagnostics.inactive_windows == 2
    assert diagnostics.active_pct == 50.0
    assert diagnostics.positive_active_windows == 2
    assert diagnostics.positive_active_pct == 100.0
    assert diagnostics.positive_all_pct == 50.0


def test_activity_diagnostics_is_safe_when_all_windows_are_inactive():
    result = _result([
        _window(0, 0, 0.0),
        _window(1, 0, 0.0),
    ])

    diagnostics = RobustnessDiagnosticsServiceV083.evaluate(result)

    assert diagnostics.active_windows == 0
    assert diagnostics.positive_active_pct == 0.0
    assert diagnostics.active_pct == 0.0
