from datetime import datetime, timezone

from edward.services.parameter_zone_oos_diagnostics_v084 import ParameterZoneOOSDiagnosticsServiceV084
from edward.services.parameter_zone_v084 import ParameterZoneV084
from edward.services.robust_walk_forward_service_v08 import WalkForwardWindowResult


def _window(index: int, oos_return: float, sharpe: float = 1.0, dd: float = 2.0) -> WalkForwardWindowResult:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return WalkForwardWindowResult(
        index=index,
        train_start=now,
        train_end=now,
        test_start=now,
        test_end=now,
        parameters={"lookback": 20},
        train_score=80.0,
        test_net_return_pct=oos_return,
        test_benchmark_return_pct=0.0,
        test_excess_return_pct=oos_return,
        test_max_drawdown_pct=dd,
        test_sharpe=sharpe,
        test_sortino=sharpe,
        test_trades=3,
    )


def _zone(stable: bool) -> ParameterZoneV084:
    return ParameterZoneV084(
        strategy="Breakout",
        candidates=3,
        viable_candidates=2 if stable else 1,
        representative_parameters={"lookback": 20},
        parameter_keys=((('lookback', 20),),),
        mean_score=1.0,
        median_score=1.0,
        score_dispersion=0.1,
        viability_pct=66.6667,
        neighborhood_stability_pct=75.0 if stable else 25.0,
        stable=stable,
    )


def test_oos_diagnostics_compare_train_fixed_zone_labels() -> None:
    result = ParameterZoneOOSDiagnosticsServiceV084.evaluate(
        strategy="Breakout",
        windows=[_window(0, 2.0), _window(1, -1.0)],
        zones=[_zone(True), _zone(False)],
    )
    assert result.stable_windows == 1
    assert result.point_optimum_windows == 1
    assert result.stable_positive_oos_pct == 100.0
    assert result.point_optimum_positive_oos_pct == 0.0
    assert result.oos_return_delta_pct == 3.0
    assert result.oos_positive_delta_pct == 100.0


def test_oos_diagnostics_does_not_reclassify_zone_from_oos_result() -> None:
    zones = [_zone(False), _zone(True)]
    result = ParameterZoneOOSDiagnosticsServiceV084.evaluate(
        strategy="Breakout",
        windows=[_window(0, 10.0), _window(1, -10.0)],
        zones=zones,
    )
    assert result.stable_windows == 1
    assert result.point_optimum_windows == 1
    assert result.stable_mean_oos_return_pct == -10.0
    assert result.point_optimum_mean_oos_return_pct == 10.0
