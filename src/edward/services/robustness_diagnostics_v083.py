from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev

from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult


@dataclass(frozen=True, slots=True)
class RobustnessDiagnosticsV083:
    return_consistency_score: float
    risk_consistency_score: float
    sharpe_consistency_score: float
    parameter_stability_score: float
    performance_consistency_score: float
    return_contribution: float
    risk_contribution: float
    sharpe_contribution: float
    parameter_stability_contribution: float
    performance_consistency_contribution: float
    robustness_total: float
    total_windows: int
    active_windows: int
    inactive_windows: int
    positive_active_windows: int
    positive_active_pct: float
    positive_all_pct: float
    active_pct: float


class RobustnessDiagnosticsServiceV083:
    """Explains the existing v0.8 robustness formula without changing it."""

    WEIGHTS = {
        "return": 0.35,
        "risk": 0.20,
        "sharpe": 0.15,
        "stability": 0.15,
        "performance": 0.15,
    }

    @classmethod
    def evaluate(cls, result: RobustWalkForwardResult) -> RobustnessDiagnosticsV083:
        windows = tuple(result.windows)
        total = len(windows)
        active = sum(item.test_trades > 0 for item in windows)
        inactive = total - active
        positive_active = sum(item.test_trades > 0 and item.test_net_return_pct > 0 for item in windows)
        positive_all = sum(item.test_net_return_pct > 0 for item in windows)

        returns = [item.test_net_return_pct for item in windows]
        dispersion_penalty = pstdev(returns) / max(abs(mean(returns)), 1.0) * 10 if returns else 0.0
        performance_consistency = max(0.0, min(100.0, 100.0 - dispersion_penalty))

        scores = {
            "return": result.return_consistency_pct,
            "risk": result.risk_consistency_pct,
            "sharpe": result.sharpe_consistency_pct,
            "stability": result.parameter_stability.stability_pct,
            "performance": performance_consistency,
        }
        contributions = {key: scores[key] * cls.WEIGHTS[key] for key in scores}

        return RobustnessDiagnosticsV083(
            return_consistency_score=scores["return"],
            risk_consistency_score=scores["risk"],
            sharpe_consistency_score=scores["sharpe"],
            parameter_stability_score=scores["stability"],
            performance_consistency_score=scores["performance"],
            return_contribution=contributions["return"],
            risk_contribution=contributions["risk"],
            sharpe_contribution=contributions["sharpe"],
            parameter_stability_contribution=contributions["stability"],
            performance_consistency_contribution=contributions["performance"],
            robustness_total=round(sum(contributions.values()), 2),
            total_windows=total,
            active_windows=active,
            inactive_windows=inactive,
            positive_active_windows=positive_active,
            positive_active_pct=round(positive_active / active * 100, 2) if active else 0.0,
            positive_all_pct=round(positive_all / total * 100, 2) if total else 0.0,
            active_pct=round(active / total * 100, 2) if total else 0.0,
        )


__all__ = ["RobustnessDiagnosticsV083", "RobustnessDiagnosticsServiceV083"]
