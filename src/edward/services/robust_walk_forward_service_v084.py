from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass
from typing import Any, Sequence

from edward.services.economic_viability_service_v084 import EconomicViabilityServiceV084
from edward.services.parameter_zone_v084 import ParameterZoneServiceV084, ParameterZoneV084
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult, RobustWalkForwardService

ROBUST_WF_V084_VERSION = "0.8.4"
logger = logging.getLogger(__name__)

_ACTIVE_MAX_DRAWDOWN: contextvars.ContextVar[float | None] = contextvars.ContextVar("edward_v084_max_train_drawdown_pct", default=None)
_ACTIVE_MIN_TRADES: contextvars.ContextVar[int] = contextvars.ContextVar("edward_v084_min_train_trades", default=1)
_ACTIVE_STRATEGY: contextvars.ContextVar[str] = contextvars.ContextVar("edward_v084_strategy", default="unknown")
_ACTIVE_ZONES: contextvars.ContextVar[list[ParameterZoneV084] | None] = contextvars.ContextVar("edward_v084_parameter_zones", default=None)
_ACTIVE_TRAIN_TRADES: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar("edward_v084_selected_train_trades", default=None)


@dataclass(frozen=True, slots=True)
class RobustWalkForwardResultV084(RobustWalkForwardResult):
    """v0.8.4 result carrying Train-only parameter-zone and activity evidence."""

    parameter_zone_diagnostics: tuple[ParameterZoneV084, ...] = ()
    selected_train_trades: tuple[int, ...] = ()


class RobustWalkForwardServiceV084(RobustWalkForwardService):
    """v0.8.4 WF selector with Train-only economic viability, zone and activity diagnostics."""

    VERSION = ROBUST_WF_V084_VERSION

    @classmethod
    def _select_robust_parameters(cls, candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]]) -> tuple[dict[str, Any], ResearchBacktestResult, float]:
        max_drawdown_pct = _ACTIVE_MAX_DRAWDOWN.get()
        min_train_trades = _ACTIVE_MIN_TRADES.get()
        strategy = _ACTIVE_STRATEGY.get()
        viable: list[tuple[dict[str, Any], ResearchBacktestResult]] = []
        logger.warning("[V084 WF VIABILITY FILTER] candidates=%d max_train_dd=%s min_train_trades=%d", len(candidates), max_drawdown_pct, min_train_trades)
        for params, result in candidates:
            decision = EconomicViabilityServiceV084.evaluate(result, min_excess_return_pct=0.0, max_drawdown_pct=max_drawdown_pct, min_trades=min_train_trades)
            logger.warning("[V084 WF CANDIDATE] params=%s eligible=%s reasons=%s train_excess=%.4f train_return=%.4f train_dd=%.4f trades=%d", params, decision.eligible, decision.reasons, result.excess_return_pct, result.net_return_pct, result.max_drawdown_pct, result.trades)
            if decision.eligible:
                viable.append((params, result))
        logger.warning("[V084 WF VIABILITY RESULT] total=%d viable=%d rejected=%d", len(candidates), len(viable), len(candidates) - len(viable))
        if not viable:
            logger.warning("[V084 WF NO VIABLE PARAMETER] no Train candidate passed economic viability; production parameter selection aborted")
            raise ValueError("No economically viable Train parameter candidate")

        selected = super()._select_robust_parameters(viable)
        zone = ParameterZoneServiceV084.evaluate(strategy=strategy, candidates=candidates, viable=viable, anchor_parameters=selected[0])
        zones = _ACTIVE_ZONES.get()
        if zones is not None:
            zones.append(zone)
        zone_risk = "STABLE_ZONE" if zone.stable else "POINT_OPTIMUM"
        logger.warning("[V084 PARAMETER ZONE RISK] strategy=%s risk=%s representative=%s robust_winner=%s viable=%d/%d viability_pct=%.2f stability=%.2f", strategy, zone_risk, zone.representative_parameters, selected[0], zone.viable_candidates, zone.candidates, zone.viability_pct, zone.neighborhood_stability_pct)
        logger.warning("[V084 WF VIABLE SELECTION] selected=%s robust_train_score=%.2f viable_candidates=%d zone_risk=%s", selected[0], selected[2], len(viable), zone_risk)
        return selected

    @staticmethod
    def _with_diagnostics(result: RobustWalkForwardResult, zones: Sequence[ParameterZoneV084], train_trades: Sequence[int]) -> RobustWalkForwardResultV084:
        return RobustWalkForwardResultV084(
            strategy=result.strategy, windows=result.windows,
            mean_test_return_pct=result.mean_test_return_pct, median_test_return_pct=result.median_test_return_pct,
            std_test_return_pct=result.std_test_return_pct, worst_test_return_pct=result.worst_test_return_pct,
            best_test_return_pct=result.best_test_return_pct, mean_test_drawdown_pct=result.mean_test_drawdown_pct,
            mean_test_sharpe=result.mean_test_sharpe, positive_return_windows=result.positive_return_windows,
            risk_ok_windows=result.risk_ok_windows, positive_sharpe_windows=result.positive_sharpe_windows,
            return_consistency_pct=result.return_consistency_pct, risk_consistency_pct=result.risk_consistency_pct,
            sharpe_consistency_pct=result.sharpe_consistency_pct, robustness_score=result.robustness_score,
            parameter_stability=result.parameter_stability, version=result.version,
            parameter_zone_diagnostics=tuple(zones), selected_train_trades=tuple(train_trades),
        )

    @classmethod
    def run(cls, *, candles, strategy: str, parameter_grid, signal_factory, train_size: int, test_size: int, costs: BacktestCostModel | None = None, max_drawdown_pct: float | None = None, min_train_trades: int = 1):
        drawdown_token = _ACTIVE_MAX_DRAWDOWN.set(max_drawdown_pct)
        trades_token = _ACTIVE_MIN_TRADES.set(min_train_trades)
        strategy_token = _ACTIVE_STRATEGY.set(strategy)
        zones_token = _ACTIVE_ZONES.set([])
        train_trades_token = _ACTIVE_TRAIN_TRADES.set([])
        try:
            logger.warning("[V084 WF START] strategy=%s train=%d test=%d max_train_dd=%s min_train_trades=%d", strategy, train_size, test_size, max_drawdown_pct, min_train_trades)
            result = super().run(candles=candles, strategy=strategy, parameter_grid=parameter_grid, signal_factory=signal_factory, train_size=train_size, test_size=test_size, costs=costs, max_drawdown_pct=max_drawdown_pct)
            zones = tuple(_ACTIVE_ZONES.get() or ())
            train_trades = tuple(_ACTIVE_TRAIN_TRADES.get() or ())
            result_v084 = cls._with_diagnostics(result, zones, train_trades)
            logger.warning("[V084 TRAIN ACTIVITY RESULT] strategy=%s windows=%d no_trades=%d low_sample=%d adequate_sample=%d mean_train_trades=%.2f", strategy, len(train_trades), sum(t == 0 for t in train_trades), sum(0 < t < 5 for t in train_trades), sum(t >= 5 for t in train_trades), sum(train_trades) / len(train_trades) if train_trades else 0.0)
            logger.warning("[V084 PARAMETER ZONE RESULT AGGREGATE] strategy=%s windows=%d zone_windows=%d stable_windows=%d point_optimum_windows=%d stable_pct=%.2f mean_viability_pct=%.2f", strategy, len(result_v084.windows), len(zones), sum(zone.stable for zone in zones), sum(not zone.stable for zone in zones), (sum(zone.stable for zone in zones) / len(zones) * 100.0) if zones else 0.0, (sum(zone.viability_pct for zone in zones) / len(zones)) if zones else 0.0)
            logger.warning("[V084 WF RESULT] strategy=%s windows=%d robustness=%.2f mean_oos_return=%.4f mean_oos_dd=%.4f mean_oos_sharpe=%.4f", strategy, len(result_v084.windows), result_v084.robustness_score, result_v084.mean_test_return_pct, result_v084.mean_test_drawdown_pct, result_v084.mean_test_sharpe)
            return result_v084
        finally:
            _ACTIVE_MAX_DRAWDOWN.reset(drawdown_token)
            _ACTIVE_MIN_TRADES.reset(trades_token)
            _ACTIVE_STRATEGY.reset(strategy_token)
            _ACTIVE_ZONES.reset(zones_token)
            _ACTIVE_TRAIN_TRADES.reset(train_trades_token)


__all__ = ["ROBUST_WF_V084_VERSION", "RobustWalkForwardResultV084", "RobustWalkForwardServiceV084"]
