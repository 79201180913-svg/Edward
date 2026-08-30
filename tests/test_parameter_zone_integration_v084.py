from datetime import datetime, timezone

from edward.services.parameter_zone_oos_diagnostics_v084 import ParameterZoneOOSDiagnosticsServiceV084
from edward.services.parameter_zone_v084 import ParameterZoneV084
from edward.services.robust_walk_forward_service_v08 import WalkForwardWindowResult


def _window(index: int, value: float) -> WalkForwardWindowResult:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return WalkForwardWindowResult(
        index=index, train_start=now, train_end=now, test_start=now, test_end=now,
        parameters={"lookback": 20}, train_score=80.0,
        test_net_return_pct=value, test_benchmark_return_pct=0.0,
        test_excess_return_pct=value, test_max_drawdown_pct=2.0,
        test_sharpe=1.0, test_sortino=1.0, test_trades=3,
    )


def _zone(stable: bool, anchor: int = 20) -> ParameterZoneV084:
    return ParameterZoneV084(
        strategy="Breakout", candidates=3, viable_candidates=2 if stable else 1,
        representative_parameters={"lookback": anchor},
        parameter_keys=((('lookback', anchor),),), mean_score=1.0,
        median_score=1.0, score_dispersion=0.1,
        viability_pct=66.6667, neighborhood_stability_pct=75.0 if stable else 25.0,
        stable=stable,
    )


def test_zone_oos_pairing_preserves_window_order_and_labels() -> None:
    windows = [_window(0, 2.0), _window(1, -1.0)]
    zones = [_zone(True), _zone(False)]
    result = ParameterZoneOOSDiagnosticsServiceV084.evaluate(
        strategy="Breakout", windows=windows, zones=zones
    )
    assert result.windows == len(windows)
    assert result.stable_windows == 1
    assert result.point_optimum_windows == 1
    assert result.stable_mean_oos_return_pct == 2.0
    assert result.point_optimum_mean_oos_return_pct == -1.0


def test_oos_values_cannot_reclassify_fixed_train_zone() -> None:
    zones = [_zone(False), _zone(True)]
    result = ParameterZoneOOSDiagnosticsServiceV084.evaluate(
        strategy="Breakout", windows=[_window(0, 100.0), _window(1, -100.0)], zones=zones
    )
    assert result.point_optimum_windows == 1
    assert result.stable_windows == 1
    assert result.point_optimum_mean_oos_return_pct == 100.0
    assert result.stable_mean_oos_return_pct == -100.0
