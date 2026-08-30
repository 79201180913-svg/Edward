from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from edward.services.parameter_zone_v084 import ParameterZoneV084
from edward.services.robust_walk_forward_service_v08 import WalkForwardWindowResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParameterZoneOOSDiagnosticsV084:
    windows: int
    stable_windows: int
    point_optimum_windows: int
    stable_positive_oos_pct: float
    point_optimum_positive_oos_pct: float
    stable_mean_oos_return_pct: float
    point_optimum_mean_oos_return_pct: float
    stable_mean_oos_sharpe: float
    point_optimum_mean_oos_sharpe: float
    stable_mean_oos_drawdown_pct: float
    point_optimum_mean_oos_drawdown_pct: float
    oos_return_delta_pct: float
    oos_positive_delta_pct: float


class ParameterZoneOOSDiagnosticsServiceV084:
    """Compare OOS outcomes of stable parameter zones vs point optima.

    Zone classification is produced from Train-only evidence. This service only
    joins that already-fixed classification with the corresponding OOS window
    result; it never changes zone membership or parameter selection.
    """

    @staticmethod
    def evaluate(
        *,
        strategy: str,
        windows: Sequence[WalkForwardWindowResult],
        zones: Sequence[ParameterZoneV084],
    ) -> ParameterZoneOOSDiagnosticsV084:
        pairs = list(zip(windows, zones))
        stable = [window for window, zone in pairs if zone.stable]
        point = [window for window, zone in pairs if not zone.stable]

        def positive(items: Sequence[WalkForwardWindowResult]) -> float:
            return (sum(item.test_net_return_pct > 0 for item in items) / len(items) * 100.0) if items else 0.0

        def avg(items: Sequence[WalkForwardWindowResult], attr: str) -> float:
            return mean(float(getattr(item, attr)) for item in items) if items else 0.0

        result = ParameterZoneOOSDiagnosticsV084(
            windows=len(pairs),
            stable_windows=len(stable),
            point_optimum_windows=len(point),
            stable_positive_oos_pct=round(positive(stable), 4),
            point_optimum_positive_oos_pct=round(positive(point), 4),
            stable_mean_oos_return_pct=round(avg(stable, "test_net_return_pct"), 8),
            point_optimum_mean_oos_return_pct=round(avg(point, "test_net_return_pct"), 8),
            stable_mean_oos_sharpe=round(avg(stable, "test_sharpe"), 8),
            point_optimum_mean_oos_sharpe=round(avg(point, "test_sharpe"), 8),
            stable_mean_oos_drawdown_pct=round(avg(stable, "test_max_drawdown_pct"), 8),
            point_optimum_mean_oos_drawdown_pct=round(avg(point, "test_max_drawdown_pct"), 8),
            oos_return_delta_pct=round(avg(stable, "test_net_return_pct") - avg(point, "test_net_return_pct"), 8),
            oos_positive_delta_pct=round(positive(stable) - positive(point), 4),
        )
        logger.warning(
            "[V084 PARAMETER ZONE OOS DIAGNOSTICS] strategy=%s windows=%d stable=%d point_optimum=%d stable_positive_oos=%.2f point_positive_oos=%.2f stable_mean_return=%.6f point_mean_return=%.6f return_delta=%.6f stable_sharpe=%.4f point_sharpe=%.4f stable_dd=%.4f point_dd=%.4f",
            strategy, result.windows, result.stable_windows, result.point_optimum_windows,
            result.stable_positive_oos_pct, result.point_optimum_positive_oos_pct,
            result.stable_mean_oos_return_pct, result.point_optimum_mean_oos_return_pct,
            result.oos_return_delta_pct, result.stable_mean_oos_sharpe,
            result.point_optimum_mean_oos_sharpe, result.stable_mean_oos_drawdown_pct,
            result.point_optimum_mean_oos_drawdown_pct,
        )
        return result


__all__ = ["ParameterZoneOOSDiagnosticsV084", "ParameterZoneOOSDiagnosticsServiceV084"]
