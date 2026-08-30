from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Sequence

from edward.services.robust_walk_forward_service_v08 import WalkForwardWindowResult


@dataclass(frozen=True, slots=True)
class ActiveOOSDiagnosticsV084:
    total_windows: int
    active_windows: int
    no_trade_windows: int
    active_pct: float
    mean_active_return_pct: float
    median_active_return_pct: float
    mean_active_drawdown_pct: float
    mean_active_sharpe: float
    positive_active_windows: int
    active_return_consistency_pct: float
    active_risk_consistency_pct: float
    active_sharpe_consistency_pct: float


class ActiveOOSDiagnosticsServiceV084:
    """Separates executed OOS windows from deliberate no-trade windows."""

    @staticmethod
    def evaluate(windows: Sequence[WalkForwardWindowResult], *, max_drawdown_pct: float | None = None) -> ActiveOOSDiagnosticsV084:
        values = tuple(windows)
        active = tuple(window for window in values if window.test_trades > 0)
        no_trade = tuple(window for window in values if window.test_trades == 0 and not window.parameters)
        total = len(values)
        count = len(active)
        if not active:
            return ActiveOOSDiagnosticsV084(total, 0, len(no_trade), 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0)
        returns = [window.test_net_return_pct for window in active]
        drawdowns = [window.test_max_drawdown_pct for window in active]
        sharpes = [window.test_sharpe for window in active]
        positive = sum(value > 0 for value in returns)
        risk_ok = sum(max_drawdown_pct is None or value <= max_drawdown_pct for value in drawdowns)
        positive_sharpe = sum(value > 0 for value in sharpes)
        return ActiveOOSDiagnosticsV084(
            total_windows=total,
            active_windows=count,
            no_trade_windows=len(no_trade),
            active_pct=count / total * 100 if total else 0.0,
            mean_active_return_pct=mean(returns),
            median_active_return_pct=median(returns),
            mean_active_drawdown_pct=mean(drawdowns),
            mean_active_sharpe=mean(sharpes),
            positive_active_windows=positive,
            active_return_consistency_pct=positive / count * 100,
            active_risk_consistency_pct=risk_ok / count * 100,
            active_sharpe_consistency_pct=positive_sharpe / count * 100,
        )


__all__ = ["ActiveOOSDiagnosticsV084", "ActiveOOSDiagnosticsServiceV084"]
