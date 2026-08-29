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
    baseline_oos_return_pct: float
    shadow_oos_return_pct: float
    delta_return_pct: float
    baseline_oos_sharpe: float
    shadow_oos_sharpe: float
    baseline_oos_drawdown_pct: float
    shadow_oos_drawdown_pct: float
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


class WFParameterTransferAuditServiceV083:
    """Shadow-only WF audit whose history contains every prior candidate's OOS result.

    The current window's OOS results are never available to the selector before
    selection. After the shadow choice is made, the whole candidate OOS set is
    appended to history for future windows. Production selection is untouched.
    """

    @staticmethod
    def _baseline(candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]]) -> tuple[dict[str, Any], ResearchBacktestResult]:
        return max(candidates, key=lambda item: (item[1].excess_return_pct, item[1].sharpe, -item[1].max_drawdown_pct))

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
            delta = shadow_oos.net_return_pct - baseline_oos.net_return_pct
            changed = parameter_key(selection.selected_parameters) != parameter_key(baseline_parameters)

            logger.warning(
                "[V083 TRANSFER AUDIT WINDOW] strategy=%s window=%d history_entries=%d baseline=%s shadow=%s changed=%s baseline_oos=%.4f shadow_oos=%.4f delta=%.4f",
                strategy, index, len(history), baseline_parameters, selection.selected_parameters,
                changed, baseline_oos.net_return_pct, shadow_oos.net_return_pct, delta,
            )

            windows.append(
                TransferAuditWindow(
                    index=index,
                    baseline_parameters=dict(baseline_parameters),
                    shadow_parameters=dict(selection.selected_parameters),
                    baseline_oos_return_pct=baseline_oos.net_return_pct,
                    shadow_oos_return_pct=shadow_oos.net_return_pct,
                    delta_return_pct=delta,
                    baseline_oos_sharpe=baseline_oos.sharpe,
                    shadow_oos_sharpe=shadow_oos.sharpe,
                    baseline_oos_drawdown_pct=baseline_oos.max_drawdown_pct,
                    shadow_oos_drawdown_pct=shadow_oos.max_drawdown_pct,
                    changed=changed,
                    history_entries_before_window=len(history),
                )
            )

            # Critical invariant: append ALL candidates only after this window's
            # shadow selection has been completed. Future windows may use these
            # entries; this window never can.
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
        logger.warning(
            "[V083 TRANSFER AUDIT RESULT] strategy=%s windows=%d changed_windows=%d changed_pct=%.2f positive_changed=%d negative_changed=%d positive_delta_pct=%.2f mean_changed_delta=%.4f median_changed_delta=%.4f cumulative_changed_delta=%.4f",
            strategy, len(windows), changed, changed / len(windows) * 100.0, positive, negative,
            positive / changed * 100.0 if changed else 0.0, mean_delta, median_delta, sum(deltas),
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
        )


__all__ = ["TransferAuditWindow", "TransferAuditResult", "WFParameterTransferAuditServiceV083"]
