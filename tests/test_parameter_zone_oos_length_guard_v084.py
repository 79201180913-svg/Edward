from datetime import datetime, timezone
import pytest

from edward.services.parameter_zone_oos_diagnostics_v084 import ParameterZoneOOSDiagnosticsServiceV084
from edward.services.parameter_zone_v084 import ParameterZoneV084
from edward.services.robust_walk_forward_service_v08 import WalkForwardWindowResult


def _window(index: int) -> WalkForwardWindowResult:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return WalkForwardWindowResult(index=index, train_start=now, train_end=now, test_start=now, test_end=now, parameters={}, train_score=0.0, test_net_return_pct=0.0, test_benchmark_return_pct=0.0, test_excess_return_pct=0.0, test_max_drawdown_pct=0.0, test_sharpe=0.0, test_sortino=0.0, test_trades=0)


def _zone() -> ParameterZoneV084:
    return ParameterZoneV084(strategy="Breakout", candidates=1, viable_candidates=1, representative_parameters={}, parameter_keys=(), mean_score=0.0, median_score=0.0, score_dispersion=0.0, viability_pct=100.0, neighborhood_stability_pct=100.0, stable=True)


def test_oos_diagnostics_rejects_mismatched_window_and_zone_counts() -> None:
    with pytest.raises(ValueError, match="same length"):
        ParameterZoneOOSDiagnosticsServiceV084.evaluate(strategy="Breakout", windows=[_window(0), _window(1)], zones=[_zone()])
