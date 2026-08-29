from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean
from typing import Any, Callable, Iterable, Sequence

from edward.services.analysis_service import Candle
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult, ResearchBacktestService
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardService
from edward.services.wf_parameter_transfer_service_v083 import WFParameterTransferSelectorV083

WF_PARAMETER_TRANSFER_SHADOW_V083_VERSION = "0.8.3"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParameterTransferWindowComparison:
    index: int
    baseline_parameters: dict[str, Any]
    shadow_parameters: dict[str, Any]
    baseline_oos_return_pct: float
    shadow_oos_return_pct: float
    baseline_oos_sharpe: float
    shadow_oos_sharpe: float
    baseline_oos_drawdown_pct: float
    shadow_oos_drawdown_pct: float
    baseline_oos_rank: int
    shadow_oos_rank: int

    @property
    def shadow_improved_return(self) -> bool:
        return self.shadow_oos_return_pct > self.baseline_oos_return_pct

    @property
    def shadow_improved_sharpe(self) -> bool:
        return self.shadow_oos_sharpe > self.baseline_oos_sharpe


@dataclass(frozen=True, slots=True)
class ParameterTransferShadowResult:
    strategy: str
    windows: tuple[ParameterTransferWindowComparison, ...]
    baseline_mean_oos_return_pct: float
    shadow_mean_oos_return_pct: float
    baseline_mean_oos_sharpe: float
    shadow_mean_oos_sharpe: float
    baseline_mean_oos_drawdown_pct: float
    shadow_mean_oos_drawdown_pct: float
    baseline_transfer_match_pct: float
    shadow_transfer_match_pct: float
    shadow_improved_return_windows: int
    shadow_improved_sharpe_windows: int
    shadow_changed_windows: int

    @property
    def mean_return_delta_pct(self) -> float:
        return self.shadow_mean_oos_return_pct - self.baseline_mean_oos_return_pct

    @property
    def mean_sharpe_delta(self) -> float:
        return self.shadow_mean_oos_sharpe - self.baseline_mean_oos_sharpe

    @property
    def mean_drawdown_delta_pct(self) -> float:
        return self.shadow_mean_oos_drawdown_pct - self.baseline_mean_oos_drawdown_pct


class WFParameterTransferShadowServiceV083:
    """Compare the new train-only selector with the existing v0.8 selector.

    This service is diagnostic/shadow only. It does not alter RobustWalkForwardService,
    Quality Gate rules, or the production-selected parameters.
    """

    @staticmethod
    def _baseline_sort_key(item: tuple[dict[str, Any], ResearchBacktestResult]) -> tuple[float, float, float]:
        result = item[1]
        return result.excess_return_pct, result.sharpe, -result.max_drawdown_pct

    @classmethod
    def run(
        cls,
        *,
        candles: Iterable[Candle],
        strategy: str,
        parameter_grid: Sequence[dict[str, Any]],
        signal_factory: Callable[[str, dict[str, Any]], Callable[[Sequence[Candle], int], bool]],
        train_size: int,
        test_size: int,
        costs: BacktestCostModel | None = None,
    ) -> ParameterTransferShadowResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if train_size < 2 or test_size < 1:
            raise ValueError("train_size must be >= 2 and test_size must be >= 1")
        if not parameter_grid:
            raise ValueError("parameter_grid cannot be empty")

        comparisons: list[ParameterTransferWindowComparison] = []
        start = 0
        while start + train_size + test_size <= len(ordered):
            train = ordered[start:start + train_size]
            test = ordered[start + train_size:start + train_size + test_size]
            index = len(comparisons)

            train_candidates: list[tuple[dict[str, Any], ResearchBacktestResult]] = []
            for params in parameter_grid:
                result = ResearchBacktestService.run(
                    candles=train,
                    strategy=strategy,
                    parameters=params,
                    signal_fn=signal_factory(strategy, params),
                    costs=costs,
                )
                train_candidates.append((dict(params), result))

            baseline_parameters, _ = max(train_candidates, key=cls._baseline_sort_key)
            shadow_selection = WFParameterTransferSelectorV083.select(
                train_candidates,
                baseline_parameters=baseline_parameters,
            )
            shadow_parameters = shadow_selection.selected_parameters

            oos_candidates: list[tuple[dict[str, Any], ResearchBacktestResult]] = []
            for params, _ in train_candidates:
                result = ResearchBacktestService.run(
                    candles=test,
                    strategy=strategy,
                    parameters=params,
                    signal_fn=signal_factory(strategy, params),
                    costs=costs,
                )
                oos_candidates.append((dict(params), result))

            ranked = sorted(
                oos_candidates,
                key=lambda item: (item[1].net_return_pct, item[1].sharpe, -item[1].max_drawdown_pct),
                reverse=True,
            )
            rank_by_key = {
                tuple(sorted(params.items())): rank
                for rank, (params, _) in enumerate(ranked, start=1)
            }
            result_by_key = {
                tuple(sorted(params.items())): result
                for params, result in oos_candidates
            }
            baseline_key = tuple(sorted(baseline_parameters.items()))
            shadow_key = tuple(sorted(shadow_parameters.items()))
            baseline_oos = result_by_key[baseline_key]
            shadow_oos = result_by_key[shadow_key]

            comparison = ParameterTransferWindowComparison(
                index=index,
                baseline_parameters=dict(baseline_parameters),
                shadow_parameters=dict(shadow_parameters),
                baseline_oos_return_pct=baseline_oos.net_return_pct,
                shadow_oos_return_pct=shadow_oos.net_return_pct,
                baseline_oos_sharpe=baseline_oos.sharpe,
                shadow_oos_sharpe=shadow_oos.sharpe,
                baseline_oos_drawdown_pct=baseline_oos.max_drawdown_pct,
                shadow_oos_drawdown_pct=shadow_oos.max_drawdown_pct,
                baseline_oos_rank=rank_by_key[baseline_key],
                shadow_oos_rank=rank_by_key[shadow_key],
            )
            comparisons.append(comparison)
            logger.warning(
                "[V083 WF TRANSFER SHADOW WINDOW] strategy=%s window=%d baseline=%s shadow=%s changed=%s "
                "baseline_oos_return=%.4f shadow_oos_return=%.4f delta=%.4f baseline_rank=%d shadow_rank=%d "
                "baseline_sharpe=%.4f shadow_sharpe=%.4f baseline_dd=%.4f shadow_dd=%.4f",
                strategy,
                index,
                baseline_parameters,
                shadow_parameters,
                baseline_key != shadow_key,
                baseline_oos.net_return_pct,
                shadow_oos.net_return_pct,
                shadow_oos.net_return_pct - baseline_oos.net_return_pct,
                rank_by_key[baseline_key],
                rank_by_key[shadow_key],
                baseline_oos.sharpe,
                shadow_oos.sharpe,
                baseline_oos.max_drawdown_pct,
                shadow_oos.max_drawdown_pct,
            )
            start += test_size

        count = len(comparisons)
        if not count:
            return ParameterTransferShadowResult(strategy, (), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0)

        baseline_returns = [item.baseline_oos_return_pct for item in comparisons]
        shadow_returns = [item.shadow_oos_return_pct for item in comparisons]
        baseline_sharpes = [item.baseline_oos_sharpe for item in comparisons]
        shadow_sharpes = [item.shadow_oos_sharpe for item in comparisons]
        baseline_dd = [item.baseline_oos_drawdown_pct for item in comparisons]
        shadow_dd = [item.shadow_oos_drawdown_pct for item in comparisons]
        baseline_matches = sum(item.baseline_oos_rank == 1 for item in comparisons)
        shadow_matches = sum(item.shadow_oos_rank == 1 for item in comparisons)
        improved_returns = sum(item.shadow_improved_return for item in comparisons)
        improved_sharpes = sum(item.shadow_improved_sharpe for item in comparisons)
        changed = sum(item.baseline_parameters != item.shadow_parameters for item in comparisons)

        result = ParameterTransferShadowResult(
            strategy=strategy,
            windows=tuple(comparisons),
            baseline_mean_oos_return_pct=mean(baseline_returns),
            shadow_mean_oos_return_pct=mean(shadow_returns),
            baseline_mean_oos_sharpe=mean(baseline_sharpes),
            shadow_mean_oos_sharpe=mean(shadow_sharpes),
            baseline_mean_oos_drawdown_pct=mean(baseline_dd),
            shadow_mean_oos_drawdown_pct=mean(shadow_dd),
            baseline_transfer_match_pct=baseline_matches / count * 100.0,
            shadow_transfer_match_pct=shadow_matches / count * 100.0,
            shadow_improved_return_windows=improved_returns,
            shadow_improved_sharpe_windows=improved_sharpes,
            shadow_changed_windows=changed,
        )
        logger.warning(
            "[V083 WF TRANSFER SHADOW RESULT] strategy=%s windows=%d changed_windows=%d "
            "baseline_mean_oos_return=%.4f shadow_mean_oos_return=%.4f return_delta=%.4f "
            "baseline_mean_oos_sharpe=%.4f shadow_mean_oos_sharpe=%.4f sharpe_delta=%.4f "
            "baseline_mean_oos_dd=%.4f shadow_mean_oos_dd=%.4f dd_delta=%.4f "
            "baseline_transfer_match_pct=%.2f shadow_transfer_match_pct=%.2f "
            "shadow_improved_return_windows=%d shadow_improved_sharpe_windows=%d",
            strategy,
            count,
            changed,
            result.baseline_mean_oos_return_pct,
            result.shadow_mean_oos_return_pct,
            result.mean_return_delta_pct,
            result.baseline_mean_oos_sharpe,
            result.shadow_mean_oos_sharpe,
            result.mean_sharpe_delta,
            result.baseline_mean_oos_drawdown_pct,
            result.shadow_mean_oos_drawdown_pct,
            result.mean_drawdown_delta_pct,
            result.baseline_transfer_match_pct,
            result.shadow_transfer_match_pct,
            improved_returns,
            improved_sharpes,
        )
        return result


__all__ = [
    "WF_PARAMETER_TRANSFER_SHADOW_V083_VERSION",
    "ParameterTransferWindowComparison",
    "ParameterTransferShadowResult",
    "WFParameterTransferShadowServiceV083",
]
