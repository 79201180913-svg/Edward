from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Callable, Iterable, Sequence

from edward.services.analysis_service import Candle
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult, ResearchBacktestService
from edward.services.wf_parameter_stability_diagnostics_v08 import parameter_key, selection_confidence, winner_margin_pct, neighborhood_stability_pct
from edward.services.wf_parameter_transfer_service_v083 import ParameterTransferHistoryEntry, WFParameterTransferSelectorV083

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TransferAuditWindow:
    index: int
    baseline_parameters: dict[str, Any]
    shadow_parameters: dict[str, Any]
    oracle_parameters: dict[str, Any]
    baseline_oos_return_pct: float
    shadow_oos_return_pct: float
    oracle_oos_return_pct: float
    delta_return_pct: float
    oracle_delta_return_pct: float
    baseline_oos_sharpe: float
    shadow_oos_sharpe: float
    oracle_oos_sharpe: float
    baseline_oos_drawdown_pct: float
    shadow_oos_drawdown_pct: float
    oracle_oos_drawdown_pct: float
    baseline_trades: int
    shadow_trades: int
    oracle_trades: int
    baseline_activity: str
    shadow_activity: str
    oracle_activity: str
    changed: bool
    history_entries_before_window: int


@dataclass(frozen=True, slots=True)
class TransferAuditResult:
    strategy: str
    windows: tuple[TransferAuditWindow, ...]
    changed_windows: int
    positive_delta_windows: int
    negative_delta_windows: int
    mean_delta_pct: float
    median_delta_pct: float
    cumulative_delta_pct: float
    positive_delta_pct: float
    baseline_active_windows: int = 0
    baseline_inactive_windows: int = 0
    baseline_active_positive_windows: int = 0
    baseline_active_negative_windows: int = 0
    shadow_active_windows: int = 0
    shadow_inactive_windows: int = 0
    shadow_active_positive_windows: int = 0
    shadow_active_negative_windows: int = 0
    oracle_active_windows: int = 0
    oracle_inactive_windows: int = 0
    oracle_active_positive_windows: int = 0
    oracle_active_negative_windows: int = 0
    baseline_mean_oos_return_pct: float = 0.0
    shadow_mean_oos_return_pct: float = 0.0
    oracle_mean_oos_return_pct: float = 0.0
    oracle_mean_delta_pct: float = 0.0


class WFParameterTransferAuditServiceV083:
    """Shadow-only WF audit with activity classification and OOS oracle evidence.

    Selection remains train-only. The current window OOS results are used only
    after shadow selection for audit and then appended to future history.
    """

    @staticmethod
    def _baseline(candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]]) -> tuple[dict[str, Any], ResearchBacktestResult]:
        return max(candidates, key=lambda item: (item[1].excess_return_pct, item[1].sharpe, -item[1].max_drawdown_pct))

    @staticmethod
    def _oracle(candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]]) -> tuple[dict[str, Any], ResearchBacktestResult]:
        return max(candidates, key=lambda item: (item[1].net_return_pct, item[1].sharpe, -item[1].max_drawdown_pct))

    @staticmethod
    def _activity(result: ResearchBacktestResult) -> str:
        if result.trades <= 0:
            return "INACTIVE"
        return "ACTIVE_POSITIVE" if result.net_return_pct > 0.0 else "ACTIVE_NEGATIVE"

    @staticmethod
    def _history_entry(window_index: int, parameters: dict[str, Any], result: ResearchBacktestResult, confidence: float) -> ParameterTransferHistoryEntry:
        return ParameterTransferHistoryEntry(
            window_index=window_index,
            parameters=dict(parameters),
            oos_net_return_pct=result.net_return_pct,
            oos_sharpe=result.sharpe,
            oos_drawdown_pct=result.max_drawdown_pct,
            selection_confidence=confidence,
        )

    @staticmethod
    def _activity_counts(windows: Sequence[TransferAuditWindow], prefix: str) -> tuple[int, int, int, int]:
        activities = [getattr(window, f"{prefix}_activity") for window in windows]
        active = sum(value != "INACTIVE" for value in activities)
        inactive = sum(value == "INACTIVE" for value in activities)
        positive = sum(value == "ACTIVE_POSITIVE" for value in activities)
        negative = sum(value == "ACTIVE_NEGATIVE" for value in activities)
        return active, inactive, positive, negative

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
    ) -> TransferAuditResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if train_size < 2 or test_size < 1:
            raise ValueError("train_size must be >= 2 and test_size must be >= 1")
        if not parameter_grid:
            raise ValueError("parameter_grid cannot be empty")

        history: list[ParameterTransferHistoryEntry] = []
        windows: list[TransferAuditWindow] = []
        start = 0

        while start + train_size + test_size <= len(ordered):
            index = len(windows)
            train = ordered[start:start + train_size]
            test = ordered[start + train_size:start + train_size + test_size]

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

            baseline_parameters, _ = cls._baseline(train_candidates)
            margin = winner_margin_pct(train_candidates)
            neighborhood, _ = neighborhood_stability_pct(baseline_parameters, train_candidates)
            confidence = selection_confidence(margin, neighborhood)

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

            selection = WFParameterTransferSelectorV083.select_with_history(
                train_candidates,
                history=history,
                baseline_parameters=baseline_parameters,
            )

            by_key = {parameter_key(params): result for params, result in oos_candidates}
            baseline_oos = by_key[parameter_key(baseline_parameters)]
            shadow_oos = by_key[parameter_key(selection.selected_parameters)]
            oracle_parameters, oracle_oos = cls._oracle(oos_candidates)
            delta = shadow_oos.net_return_pct - baseline_oos.net_return_pct
            oracle_delta = oracle_oos.net_return_pct - baseline_oos.net_return_pct
            changed = parameter_key(selection.selected_parameters) != parameter_key(baseline_parameters)
            baseline_activity = cls._activity(baseline_oos)
            shadow_activity = cls._activity(shadow_oos)
            oracle_activity = cls._activity(oracle_oos)

            logger.warning(
                "[V083 TRANSFER AUDIT WINDOW] strategy=%s window=%d history_entries=%d baseline=%s shadow=%s oracle=%s changed=%s baseline_oos=%.4f shadow_oos=%.4f oracle_oos=%.4f delta=%.4f oracle_delta=%.4f baseline_activity=%s shadow_activity=%s oracle_activity=%s",
                strategy, index, len(history), baseline_parameters, selection.selected_parameters, oracle_parameters,
                changed, baseline_oos.net_return_pct, shadow_oos.net_return_pct, oracle_oos.net_return_pct,
                delta, oracle_delta, baseline_activity, shadow_activity, oracle_activity,
            )

            windows.append(
                TransferAuditWindow(
                    index=index,
                    baseline_parameters=dict(baseline_parameters),
                    shadow_parameters=dict(selection.selected_parameters),
                    oracle_parameters=dict(oracle_parameters),
                    baseline_oos_return_pct=baseline_oos.net_return_pct,
                    shadow_oos_return_pct=shadow_oos.net_return_pct,
                    oracle_oos_return_pct=oracle_oos.net_return_pct,
                    delta_return_pct=delta,
                    oracle_delta_return_pct=oracle_delta,
                    baseline_oos_sharpe=baseline_oos.sharpe,
                    shadow_oos_sharpe=shadow_oos.sharpe,
                    oracle_oos_sharpe=oracle_oos.sharpe,
                    baseline_oos_drawdown_pct=baseline_oos.max_drawdown_pct,
                    shadow_oos_drawdown_pct=shadow_oos.max_drawdown_pct,
                    oracle_oos_drawdown_pct=oracle_oos.max_drawdown_pct,
                    baseline_trades=baseline_oos.trades,
                    shadow_trades=shadow_oos.trades,
                    oracle_trades=oracle_oos.trades,
                    baseline_activity=baseline_activity,
                    shadow_activity=shadow_activity,
                    oracle_activity=oracle_activity,
                    changed=changed,
                    history_entries_before_window=len(history),
                )
            )

            for params, result in oos_candidates:
                history.append(cls._history_entry(index, params, result, confidence))
            logger.warning(
                "[V083 TRANSFER AUDIT HISTORY] strategy=%s window=%d appended_candidates=%d history_entries=%d",
                strategy, index, len(oos_candidates), len(history),
            )

            start += test_size

        if not windows:
            return TransferAuditResult(strategy, (), 0, 0, 0, 0.0, 0.0, 0.0, 0.0)

        deltas = [window.delta_return_pct for window in windows if window.changed]
        changed = len(deltas)
        positive = sum(delta > 0.0 for delta in deltas)
        negative = sum(delta < 0.0 for delta in deltas)
        mean_delta = mean(deltas) if deltas else 0.0
        median_delta = median(deltas) if deltas else 0.0
        baseline_active, baseline_inactive, baseline_positive, baseline_negative = cls._activity_counts(windows, "baseline")
        shadow_active, shadow_inactive, shadow_positive, shadow_negative = cls._activity_counts(windows, "shadow")
        oracle_active, oracle_inactive, oracle_positive, oracle_negative = cls._activity_counts(windows, "oracle")
        baseline_mean = mean(window.baseline_oos_return_pct for window in windows)
        shadow_mean = mean(window.shadow_oos_return_pct for window in windows)
        oracle_mean = mean(window.oracle_oos_return_pct for window in windows)
        oracle_mean_delta = oracle_mean - baseline_mean

        logger.warning(
            "[V083 TRANSFER AUDIT RESULT] strategy=%s windows=%d changed_windows=%d changed_pct=%.2f positive_changed=%d negative_changed=%d positive_delta_pct=%.2f mean_changed_delta=%.4f median_changed_delta=%.4f cumulative_changed_delta=%.4f",
            strategy, len(windows), changed, changed / len(windows) * 100.0, positive, negative,
            positive / changed * 100.0 if changed else 0.0, mean_delta, median_delta, sum(deltas),
        )
        logger.warning(
            "[V083 WF ACTIVITY RESULT] strategy=%s windows=%d baseline_active=%d baseline_inactive=%d baseline_active_positive=%d baseline_active_negative=%d shadow_active=%d shadow_inactive=%d shadow_active_positive=%d shadow_active_negative=%d oracle_active=%d oracle_inactive=%d oracle_active_positive=%d oracle_active_negative=%d baseline_active_pct=%.2f shadow_active_pct=%.2f oracle_active_pct=%.2f",
            strategy, len(windows), baseline_active, baseline_inactive, baseline_positive, baseline_negative,
            shadow_active, shadow_inactive, shadow_positive, shadow_negative,
            oracle_active, oracle_inactive, oracle_positive, oracle_negative,
            baseline_active / len(windows) * 100.0,
            shadow_active / len(windows) * 100.0,
            oracle_active / len(windows) * 100.0,
        )
        logger.warning(
            "[V083 WF BASELINE TRANSFER ORACLE RESULT] strategy=%s baseline_mean_oos_return=%.4f transfer_mean_oos_return=%.4f oracle_mean_oos_return=%.4f transfer_vs_baseline=%.4f oracle_vs_baseline=%.4f",
            strategy, baseline_mean, shadow_mean, oracle_mean, shadow_mean - baseline_mean, oracle_mean_delta,
        )
        return TransferAuditResult(
            strategy=strategy,
            windows=tuple(windows),
            changed_windows=changed,
            positive_delta_windows=positive,
            negative_delta_windows=negative,
            mean_delta_pct=mean_delta,
            median_delta_pct=median_delta,
            cumulative_delta_pct=sum(deltas),
            positive_delta_pct=positive / changed * 100.0 if changed else 0.0,
            baseline_active_windows=baseline_active,
            baseline_inactive_windows=baseline_inactive,
            baseline_active_positive_windows=baseline_positive,
            baseline_active_negative_windows=baseline_negative,
            shadow_active_windows=shadow_active,
            shadow_inactive_windows=shadow_inactive,
            shadow_active_positive_windows=shadow_positive,
            shadow_active_negative_windows=shadow_negative,
            oracle_active_windows=oracle_active,
            oracle_inactive_windows=oracle_inactive,
            oracle_active_positive_windows=oracle_positive,
            oracle_active_negative_windows=oracle_negative,
            baseline_mean_oos_return_pct=baseline_mean,
            shadow_mean_oos_return_pct=shadow_mean,
            oracle_mean_oos_return_pct=oracle_mean,
            oracle_mean_delta_pct=oracle_mean_delta,
        )


__all__ = ["TransferAuditWindow", "TransferAuditResult", "WFParameterTransferAuditServiceV083"]
