from datetime import datetime, timezone

from edward.services.active_oos_diagnostics_v084 import ActiveOOSDiagnosticsServiceV084
from edward.services.robust_walk_forward_service_v08 import WalkForwardWindowResult


def window(index: int, params: dict, ret: float, dd: float, sharpe: float, trades: int) -> WalkForwardWindowResult:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return WalkForwardWindowResult(index, ts, ts, ts, ts, params, 1.0, ret, 0.0, ret, dd, sharpe, sharpe, trades)


def test_active_oos_excludes_explicit_no_trade_windows() -> None:
    result = ActiveOOSDiagnosticsServiceV084.evaluate([
        window(0, {"lookback": 20}, 2.0, 5.0, 1.0, 3),
        window(1, {}, 0.0, 0.0, 0.0, 0),
        window(2, {"lookback": 40}, -1.0, 6.0, -0.5, 2),
    ], max_drawdown_pct=25.0)
    assert result.total_windows == 3
    assert result.active_windows == 2
    assert result.no_trade_windows == 1
    assert result.active_pct == 2 / 3 * 100
    assert result.mean_active_return_pct == 0.5
    assert result.active_return_consistency_pct == 50.0
    assert result.active_risk_consistency_pct == 100.0
    assert result.active_sharpe_consistency_pct == 50.0


def test_all_no_trade_windows_have_zero_active_metrics() -> None:
    result = ActiveOOSDiagnosticsServiceV084.evaluate([window(0, {}, 0.0, 0.0, 0.0, 0), window(1, {}, 0.0, 0.0, 0.0, 0)])
    assert result.active_windows == 0
    assert result.no_trade_windows == 2
    assert result.mean_active_return_pct == 0.0
    assert result.active_return_consistency_pct == 0.0
