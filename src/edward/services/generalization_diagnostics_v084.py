from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from edward.services.regime_conditioned_evidence_v084 import RegimeConditionedEvidence
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult
from edward.services.robustness_diagnostics_v083 import RobustnessDiagnosticsServiceV083

logger = logging.getLogger(__name__)
GENERALIZATION_V084_VERSION = "0.8.4"

StrategyArchetype = Literal["PERSISTENT", "BURST", "MEAN_REVERSION"]


@dataclass(frozen=True, slots=True)
class ActivityDiagnosticsV084:
    total_windows: int
    active_windows: int
    inactive_windows: int
    active_pct: float
    positive_active_windows: int
    positive_active_pct: float
    positive_all_pct: float
    trades: int
    trade_density: float


@dataclass(frozen=True, slots=True)
class GeneralizationDiagnosticsV084:
    strategy: str
    archetype: StrategyArchetype
    activity: ActivityDiagnosticsV084
    parameter_persistence_pct: float
    regime_coverage_pct: float
    regime_positive_pct: float
    regime_mean_excess_pct: float
    generalization_score: float


class GeneralizationDiagnosticsServiceV084:
    """Descriptive post-OOS generalization evidence.

    This service never selects production parameters and never changes QG directly.
    It consumes already completed WF/OOS results only.
    """

    ARCHETYPES: dict[str, StrategyArchetype] = {
        "Trend Following": "PERSISTENT",
        "Momentum": "PERSISTENT",
        "Breakout": "BURST",
        "Mean Reversion": "MEAN_REVERSION",
    }

    @classmethod
    def archetype(cls, strategy: str) -> StrategyArchetype:
        return cls.ARCHETYPES.get(strategy, "PERSISTENT")

    @staticmethod
    def _parameter_persistence(result: RobustWalkForwardResult) -> float:
        windows = result.windows
        if len(windows) < 2:
            return 0.0
        matches = sum(windows[i].parameters == windows[i - 1].parameters for i in range(1, len(windows)))
        return round(matches / (len(windows) - 1) * 100.0, 4)

    @staticmethod
    def _activity(result: RobustWalkForwardResult) -> ActivityDiagnosticsV084:
        diagnostics = RobustnessDiagnosticsServiceV083.evaluate(result)
        trades = sum(window.test_trades for window in result.windows)
        active = diagnostics.active_windows
        return ActivityDiagnosticsV084(
            total_windows=diagnostics.total_windows,
            active_windows=diagnostics.active_windows,
            inactive_windows=diagnostics.inactive_windows,
            active_pct=diagnostics.active_pct,
            positive_active_windows=diagnostics.positive_active_windows,
            positive_active_pct=diagnostics.positive_active_pct,
            positive_all_pct=diagnostics.positive_all_pct,
            trades=trades,
            trade_density=round(trades / active, 4) if active else 0.0,
        )

    @classmethod
    def evaluate(
        cls,
        result: RobustWalkForwardResult,
        regime_evidence: RegimeConditionedEvidence | None = None,
        *,
        ticker: str | None = None,
    ) -> GeneralizationDiagnosticsV084:
        archetype = cls.archetype(result.strategy)
        activity = cls._activity(result)
        persistence = cls._parameter_persistence(result)
        regime_coverage = regime_evidence.coverage_pct if regime_evidence else 0.0
        regime_positive = regime_evidence.positive_return_pct if regime_evidence else 0.0
        regime_excess = regime_evidence.mean_oos_excess_return_pct if regime_evidence else 0.0

        # Archetype changes interpretation of activity, not the underlying OOS data.
        if archetype == "BURST":
            activity_component = 0.5 * activity.positive_active_pct + 0.5 * min(activity.active_pct, 100.0)
        elif archetype == "MEAN_REVERSION":
            activity_component = 0.5 * activity.positive_active_pct + 0.5 * regime_positive
        else:
            activity_component = activity.positive_active_pct

        regime_component = 0.5 * regime_positive + 0.5 * min(100.0, max(0.0, 50.0 + regime_excess * 10.0)) if regime_evidence else 0.0
        # With no regime-matching windows, do not award regime evidence credit.
        generalization_score = round(
            0.40 * persistence + 0.35 * activity_component + 0.25 * regime_component,
            4,
        )
        output = GeneralizationDiagnosticsV084(
            strategy=result.strategy,
            archetype=archetype,
            activity=activity,
            parameter_persistence_pct=persistence,
            regime_coverage_pct=round(regime_coverage, 4),
            regime_positive_pct=round(regime_positive, 4),
            regime_mean_excess_pct=round(regime_excess, 8),
            generalization_score=generalization_score,
        )
        logger.warning(
            "[V084 GENERALIZATION] ticker=%s strategy=%s archetype=%s persistence=%.2f active=%.2f positive_active=%.2f positive_all=%.2f trade_density=%.4f regime_coverage=%.2f regime_positive=%.2f regime_excess=%.4f score=%.4f",
            ticker, output.strategy, output.archetype, output.parameter_persistence_pct,
            output.activity.active_pct, output.activity.positive_active_pct,
            output.activity.positive_all_pct, output.activity.trade_density,
            output.regime_coverage_pct, output.regime_positive_pct,
            output.regime_mean_excess_pct, output.generalization_score,
        )
        return output


__all__ = [
    "GENERALIZATION_V084_VERSION",
    "StrategyArchetype",
    "ActivityDiagnosticsV084",
    "GeneralizationDiagnosticsV084",
    "GeneralizationDiagnosticsServiceV084",
]
