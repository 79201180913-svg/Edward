from __future__ import annotations

import contextvars
import logging
from typing import Any, Sequence

from edward.services.economic_viability_service_v084 import EconomicViabilityServiceV084
from edward.services.parameter_zone_v084 import ParameterZoneServiceV084
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardService

ROBUST_WF_V084_VERSION = "0.8.4"
logger = logging.getLogger(__name__)


_ACTIVE_MAX_DRAWDOWN: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "edward_v084_max_train_drawdown_pct", default=None
)
_ACTIVE_MIN_TRADES: contextvars.ContextVar[int] = contextvars.ContextVar(
    "edward_v084_min_train_trades", default=1
)


class RobustWalkForwardServiceV084(RobustWalkForwardService):
    """v0.8.4 WF selector with Train-only economic viability filtering."""

    VERSION = ROBUST_WF_V084_VERSION

    @classmethod
    def _select_robust_parameters(
        cls,
        candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
    ) -> tuple[dict[str, Any], ResearchBacktestResult, float]:
        max_drawdown_pct = _ACTIVE_MAX_DRAWDOWN.get()
        min_trades = _ACTIVE_MIN_TRADES.get()
        viable: list[tuple[dict[str, Any], ResearchBacktestResult]] = []

        logger.warning(
            "[V084 WF VIABILITY FILTER] candidates=%d max_train_dd=%s min_train_trades=%d",
            len(candidates),
            max_drawdown_pct,
            min_trades,
        )

        for params, result in candidates:
            decision = EconomicViabilityServiceV084.evaluate(
                result,
                min_excess_return_pct=0.0,
                max_drawdown_pct=max_drawdown_pct,
                min_trades=min_trades,
            )
            logger.warning(
                "[V084 WF CANDIDATE] params=%s eligible=%s reasons=%s train_excess=%.4f train_return=%.4f train_dd=%.4f trades=%d",
                params,
                decision.eligible,
                decision.reasons,
                result.excess_return_pct,
                result.net_return_pct,
                result.max_drawdown_pct,
                result.trades,
            )
            if decision.eligible:
                viable.append((params, result))

        logger.warning(
            "[V084 WF VIABILITY RESULT] total=%d viable=%d rejected=%d",
            len(candidates),
            len(viable),
            len(candidates) - len(viable),
        )

        if not viable:
            logger.warning(
                "[V084 WF NO VIABLE PARAMETER] no Train candidate passed economic viability; production parameter selection aborted"
            )
            raise ValueError("No economically viable Train parameter candidate")

        zone = ParameterZoneServiceV084.evaluate(
            strategy="unknown",
            candidates=candidates,
            viable=viable,
        )
        zone_risk = "STABLE_ZONE" if zone.stable else "POINT_OPTIMUM"
        logger.warning(
            "[V084 PARAMETER ZONE RISK] risk=%s representative=%s viable=%d/%d viability_pct=%.2f stability=%.2f",
            zone_risk,
            zone.representative_parameters,
            zone.viable_candidates,
            zone.candidates,
            zone.viability_pct,
            zone.neighborhood_stability_pct,
        )

        selected = super()._select_robust_parameters(viable)
        logger.warning(
            "[V084 WF VIABLE SELECTION] selected=%s robust_train_score=%.2f viable_candidates=%d zone_risk=%s",
            selected[0],
            selected[2],
            len(viable),
            zone_risk,
        )
        return selected

    @classmethod
    def run(
        cls,
        *,
        candles,
        strategy: str,
        parameter_grid,
        signal_factory,
        train_size: int,
        test_size: int,
        costs: BacktestCostModel | None = None,
        max_drawdown_pct: float | None = None,
        min_train_trades: int = 1,
    ):
        drawdown_token = _ACTIVE_MAX_DRAWDOWN.set(max_drawdown_pct)
        trades_token = _ACTIVE_MIN_TRADES.set(min_train_trades)
        try:
            logger.warning(
                "[V084 WF START] strategy=%s train=%d test=%d max_train_dd=%s min_train_trades=%d",
                strategy,
                train_size,
                test_size,
                max_drawdown_pct,
                min_train_trades,
            )
            result = super().run(
                candles=candles,
                strategy=strategy,
                parameter_grid=parameter_grid,
                signal_factory=signal_factory,
                train_size=train_size,
                test_size=test_size,
                costs=costs,
                max_drawdown_pct=max_drawdown_pct,
            )
            logger.warning(
                "[V084 WF RESULT] strategy=%s windows=%d robustness=%.2f mean_oos_return=%.4f mean_oos_dd=%.4f mean_oos_sharpe=%.4f",
                strategy,
                len(result.windows),
                result.robustness_score,
                result.mean_test_drawdown_pct,
                result.mean_test_sharpe,
            )
            return result
        finally:
            _ACTIVE_MAX_DRAWDOWN.reset(drawdown_token)
            _ACTIVE_MIN_TRADES.reset(trades_token)


__all__ = ["ROBUST_WF_V084_VERSION", "RobustWalkForwardServiceV084"]