from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Any, Callable, Iterable, Sequence

from edward.services.analysis_service import Candle
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult, ResearchBacktestService


ROBUST_WF_VERSION = "0.8.0"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WalkForwardWindowResult:
    index: int
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any
    parameters: dict[str, Any]
    train_score: float
    test_net_return_pct: float
    test_benchmark_return_pct: float
    test_excess_return_pct: float
    test_max_drawdown_pct: float
    test_sharpe: float
    test_sortino: float
    test_trades: int


@dataclass(frozen=True, slots=True)
class ParameterStability:
    windows: int
    dominant_windows: int
    stability_pct: float
    selected_parameters: tuple[tuple[tuple[str, Any], ...], ...]


@dataclass(frozen=True, slots=True)
class RobustWalkForwardResult:
    strategy: str
    windows: tuple[WalkForwardWindowResult, ...]
    mean_test_return_pct: float
    median_test_return_pct: float
    std_test_return_pct: float
    worst_test_return_pct: float
    best_test_return_pct: float
    mean_test_drawdown_pct: float
    mean_test_sharpe: float
    positive_return_windows: int
    risk_ok_windows: int
    positive_sharpe_windows: int
    return_consistency_pct: float
    risk_consistency_pct: float
    sharpe_consistency_pct: float
    robustness_score: float
    parameter_stability: ParameterStability
    version: str = ROBUST_WF_VERSION


class RobustWalkForwardService:
    """Rolling out-of-sample research with parameter/performance robustness."""

    @staticmethod
    def _parameter_key(parameters: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(sorted(parameters.items()))

    @classmethod
    def _parameter_stability(cls, windows: Sequence[WalkForwardWindowResult]) -> ParameterStability:
        selected = tuple(cls._parameter_key(item.parameters) for item in windows)
        if not selected:
            return ParameterStability(0, 0, 0.0, ())
        counts: dict[tuple[tuple[str, Any], ...], int] = {}
        for item in selected:
            counts[item] = counts.get(item, 0) + 1
        dominant = max(counts.values())
        return ParameterStability(len(selected), dominant, dominant / len(selected) * 100.0, selected)

    @staticmethod
    def _candidate_sort_key(item: tuple[dict[str, Any], ResearchBacktestResult]) -> tuple[float, float, float]:
        result = item[1]
        return result.excess_return_pct, result.sharpe, -result.max_drawdown_pct

    @staticmethod
    def _criterion_key(criterion: str, result: ResearchBacktestResult) -> float:
        if criterion == "excess_return":
            return result.excess_return_pct
        if criterion == "sharpe":
            return result.sharpe
        if criterion == "sortino":
            return result.sortino
        if criterion == "return_dd":
            return result.net_return_pct / max(result.max_drawdown_pct, 1e-9)
        raise ValueError(f"Unknown selection diagnostic criterion: {criterion}")

    @classmethod
    def _diagnostic_composite_key(cls, result: ResearchBacktestResult, candidates: Sequence[ResearchBacktestResult]) -> float:
        """Rank-average composite used only for diagnostics, never production selection."""
        metrics = (
            ("excess_return", True),
            ("sharpe", True),
            ("sortino", True),
            ("return_dd", True),
        )
        scores: list[float] = []
        for criterion, _ in metrics:
            values = [cls._criterion_key(criterion, item) for item in candidates]
            ordered = sorted(set(values))
            value = cls._criterion_key(criterion, result)
            rank = ordered.index(value) + 1
            scores.append(rank / max(len(ordered), 1))
        return mean(scores)

    @classmethod
    def _log_selection_criteria_diagnostics(
        cls,
        *,
        strategy: str,
        window_index: int,
        train_candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        oos_candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        production_selected_params: dict[str, Any],
    ) -> tuple[dict[str, bool], dict[str, float]]:
        train_results = [result for _, result in train_candidates]
        oos_by_key = {cls._parameter_key(params): result for params, result in oos_candidates}
        train_by_key = {cls._parameter_key(params): result for params, result in train_candidates}
        criteria = ("excess_return", "sharpe", "sortino", "return_dd", "composite")
        matches: dict[str, bool] = {}
        gaps: dict[str, float] = {}
        oos_ranked: dict[str, list[tuple[tuple[tuple[str, Any], ...], float]]] = {}

        for criterion in criteria:
            if criterion == "composite":
                train_values = {key: cls._diagnostic_composite_key(result, train_results) for key, result in train_by_key.items()}
                oos_results = list(oos_by_key.values())
                oos_values = {key: cls._diagnostic_composite_key(result, oos_results) for key, result in oos_by_key.items()}
            else:
                train_values = {key: cls._criterion_key(criterion, result) for key, result in train_by_key.items()}
                oos_values = {key: cls._criterion_key(criterion, result) for key, result in oos_by_key.items()}

            train_key = max(train_values, key=train_values.get)
            oos_key = max(oos_values, key=oos_values.get)
            production_key = cls._parameter_key(production_selected_params)
            selected_oos = oos_by_key[production_key]
            winner_oos = oos_by_key[oos_key]
            matches[criterion] = train_key == oos_key
            gaps[criterion] = winner_oos.net_return_pct - selected_oos.net_return_pct
            logger.warning(
                "[V083 WF SELECTION CRITERION] strategy=%s window=%d criterion=%s "
                "train_winner=%s oos_winner=%s production_selected=%s transfer_match=%s "
                "production_oos_return=%.4f criterion_oos_winner_return=%.4f selection_gap=%.4f",
                strategy, window_index, criterion, dict(train_key), dict(oos_key), production_selected_params,
                matches[criterion], selected_oos.net_return_pct, winner_oos.net_return_pct, gaps[criterion],
            )
            ranked = sorted(oos_values.items(), key=lambda item: item[1], reverse=True)
            oos_ranked[criterion] = ranked

        for criterion in criteria:
            ranked = oos_ranked[criterion]
            for rank, (key, value) in enumerate(ranked, start=1):
                logger.warning(
                    "[V083 WF SELECTION OOS RANK] strategy=%s window=%d criterion=%s rank=%d params=%s criterion_value=%.6f oos_return=%.4f oos_sharpe=%.4f oos_dd=%.4f",
                    strategy, window_index, criterion, rank, dict(key), value,
                    oos_by_key[key].net_return_pct, oos_by_key[key].sharpe, oos_by_key[key].max_drawdown_pct,
                )
        return matches, gaps

    @classmethod
    def _log_parameter_leaderboard(cls, *, strategy: str, window_index: int, candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]], selected_params: dict[str, Any]) -> None:
        ranked = sorted(candidates, key=cls._candidate_sort_key, reverse=True)
        for rank, (params, result) in enumerate(ranked, start=1):
            logger.warning(
                "[V083 WF LEADERBOARD] strategy=%s window=%d rank=%d selected=%s params=%s train_excess=%.4f sharpe=%.4f sortino=%.4f dd=%.4f trades=%d exposure=%.2f return=%.4f benchmark=%.4f turnover=%.2f win_rate=%.2f",
                strategy, window_index, rank, params == selected_params, params,
                result.excess_return_pct, result.sharpe, result.sortino, result.max_drawdown_pct,
                result.trades, result.exposure_pct, result.net_return_pct, result.benchmark_return_pct,
                result.turnover_pct, result.win_rate_pct,
            )

    @staticmethod
    def _log_window_activity(*, strategy: str, window: WalkForwardWindowResult, test_result: ResearchBacktestResult) -> None:
        active = test_result.trades > 0
        active_bars = max(0, round(test_result.exposure_pct / 100.0 * max(0, len(test_result.equity) - 1)))
        logger.warning(
            "[V083 WF ACTIVITY] strategy=%s window=%d active=%s trades=%d active_bars=%d exposure_pct=%.2f turnover_pct=%.2f oos_return=%.4f oos_excess=%.4f dd=%.4f sharpe=%.4f",
            strategy, window.index, active, test_result.trades, active_bars, test_result.exposure_pct,
            test_result.turnover_pct, window.test_net_return_pct, window.test_excess_return_pct,
            window.test_max_drawdown_pct, window.test_sharpe,
        )

    @classmethod
    def _log_oos_parameter_transfer(cls, *, strategy: str, window_index: int, candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]], selected_params: dict[str, Any]) -> tuple[bool, float]:
        ranked = sorted(candidates, key=lambda item: (item[1].net_return_pct, item[1].sharpe, -item[1].max_drawdown_pct), reverse=True)
        selected_rank = next((rank for rank, (params, _) in enumerate(ranked, start=1) if params == selected_params), None)
        selected_result = next((result for params, result in candidates if params == selected_params), None)
        if selected_result is None or selected_rank is None or not ranked:
            return False, 0.0
        oos_winner_params, oos_winner_result = ranked[0]
        gap = oos_winner_result.net_return_pct - selected_result.net_return_pct
        logger.warning(
            "[V083 WF OOS TRANSFER] strategy=%s window=%d train_selected=%s train_selected_oos_rank=%d oos_winner=%s transfer_match=%s selected_oos_return=%.4f oos_winner_return=%.4f selection_gap=%.4f selected_oos_sharpe=%.4f oos_winner_sharpe=%.4f selected_oos_dd=%.4f oos_winner_dd=%.4f",
            strategy, window_index, selected_params, selected_rank, oos_winner_params,
            selected_params == oos_winner_params, selected_result.net_return_pct,
            oos_winner_result.net_return_pct, gap, selected_result.sharpe, oos_winner_result.sharpe,
            selected_result.max_drawdown_pct, oos_winner_result.max_drawdown_pct,
        )
        return selected_params == oos_winner_params, gap

    @classmethod
    def run(cls, *, candles: Iterable[Candle], strategy: str, parameter_grid: Sequence[dict[str, Any]], signal_factory: Callable[[str, dict[str, Any]], Callable[[Sequence[Candle], int], bool]], train_size: int, test_size: int, costs: BacktestCostModel | None = None, max_drawdown_pct: float | None = None) -> RobustWalkForwardResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if train_size < 2 or test_size < 1:
            raise ValueError("train_size must be >= 2 and test_size must be >= 1")
        if not parameter_grid:
            raise ValueError("parameter_grid cannot be empty")
        expected_windows = max(0, (len(ordered) - train_size) // test_size)
        logger.warning("[V083 WF START] strategy=%s candles=%d train=%d test=%d expected_windows=%d grid=%d max_dd=%s", strategy, len(ordered), train_size, test_size, expected_windows, len(parameter_grid), max_drawdown_pct)
        windows: list[WalkForwardWindowResult] = []
        exposures: list[float] = []
        transfer_matches = 0
        transfer_gaps: list[float] = []
        criterion_matches: dict[str, int] = {key: 0 for key in ("excess_return", "sharpe", "sortino", "return_dd", "composite")}
        criterion_gaps: dict[str, list[float]] = {key: [] for key in criterion_matches}
        start = 0
        while start + train_size + test_size <= len(ordered):
            train = ordered[start:start + train_size]
            test = ordered[start + train_size:start + train_size + test_size]
            window_index = len(windows)
            candidates: list[tuple[dict[str, Any], ResearchBacktestResult]] = []
            for params in parameter_grid:
                train_result = ResearchBacktestService.run(candles=train, strategy=strategy, parameters=params, signal_fn=signal_factory(strategy, params), costs=costs)
                candidates.append((dict(params), train_result))
            selected_params, train_result = max(candidates, key=cls._candidate_sort_key)
            cls._log_parameter_leaderboard(strategy=strategy, window_index=window_index, candidates=candidates, selected_params=selected_params)

            oos_candidates: list[tuple[dict[str, Any], ResearchBacktestResult]] = []
            for params, _ in candidates:
                oos_result = ResearchBacktestService.run(candles=test, strategy=strategy, parameters=params, signal_fn=signal_factory(strategy, params), costs=costs)
                oos_candidates.append((dict(params), oos_result))
            matches, gaps = cls._log_selection_criteria_diagnostics(
                strategy=strategy, window_index=window_index, train_candidates=candidates,
                oos_candidates=oos_candidates, production_selected_params=selected_params,
            )
            for criterion, matched in matches.items():
                criterion_matches[criterion] += int(matched)
                criterion_gaps[criterion].append(gaps[criterion])
            transfer_match, transfer_gap = cls._log_oos_parameter_transfer(strategy=strategy, window_index=window_index, candidates=oos_candidates, selected_params=selected_params)
            if transfer_match:
                transfer_matches += 1
            transfer_gaps.append(transfer_gap)
            test_result = next(result for params, result in oos_candidates if params == selected_params)
            exposures.append(test_result.exposure_pct)
            window = WalkForwardWindowResult(window_index, train[0].timestamp, train[-1].timestamp, test[0].timestamp, test[-1].timestamp, dict(selected_params), train_result.excess_return_pct, test_result.net_return_pct, test_result.benchmark_return_pct, test_result.excess_return_pct, test_result.max_drawdown_pct, test_result.sharpe, test_result.sortino, test_result.trades)
            windows.append(window)
            logger.warning("[V083 WF WINDOW] strategy=%s window=%d train=%s..%s test=%s..%s params=%s train_excess=%.4f oos_return=%.4f benchmark=%.4f excess=%.4f dd=%.4f sharpe=%.4f sortino=%.4f trades=%d", strategy, window.index, window.train_start, window.train_end, window.test_start, window.test_end, window.parameters, window.train_score, window.test_net_return_pct, window.test_benchmark_return_pct, window.test_excess_return_pct, window.test_max_drawdown_pct, window.test_sharpe, window.test_sortino, window.test_trades)
            cls._log_window_activity(strategy=strategy, window=window, test_result=test_result)
            start += test_size

        if not windows:
            logger.warning("[V083 WF EMPTY] strategy=%s candles=%d train=%d test=%d", strategy, len(ordered), train_size, test_size)
            return cls._empty(strategy)
        returns = [item.test_net_return_pct for item in windows]
        drawdowns = [item.test_max_drawdown_pct for item in windows]
        sharpes = [item.test_sharpe for item in windows]
        count = len(windows)
        positive = sum(value > 0 for value in returns)
        risk_ok = sum(max_drawdown_pct is None or value <= max_drawdown_pct for value in drawdowns)
        positive_sharpe = sum(value > 0 for value in sharpes)
        return_consistency = positive / count * 100.0
        risk_consistency = risk_ok / count * 100.0
        sharpe_consistency = positive_sharpe / count * 100.0
        stability = cls._parameter_stability(windows)
        dispersion_penalty = pstdev(returns) / max(abs(mean(returns)), 1.0) * 10.0
        performance_consistency = max(0.0, min(100.0, 100.0 - dispersion_penalty))
        robustness = round(return_consistency * 0.35 + risk_consistency * 0.20 + sharpe_consistency * 0.15 + stability.stability_pct * 0.15 + performance_consistency * 0.15, 2)
        result = RobustWalkForwardResult(strategy=strategy, windows=tuple(windows), mean_test_return_pct=mean(returns), median_test_return_pct=median(returns), std_test_return_pct=pstdev(returns) if len(returns) > 1 else 0.0, worst_test_return_pct=min(returns), best_test_return_pct=max(returns), mean_test_drawdown_pct=mean(drawdowns), mean_test_sharpe=mean(sharpes), positive_return_windows=positive, risk_ok_windows=risk_ok, positive_sharpe_windows=positive_sharpe, return_consistency_pct=return_consistency, risk_consistency_pct=risk_consistency, sharpe_consistency_pct=sharpe_consistency, robustness_score=robustness, parameter_stability=stability)
        active_windows = sum(item.test_trades > 0 for item in windows)
        logger.warning("[V083 WF ACTIVITY RESULT] strategy=%s windows=%d active_windows=%d inactive_windows=%d active_pct=%.2f total_trades=%d mean_exposure=%.2f", strategy, count, active_windows, count - active_windows, active_windows / count * 100.0, sum(item.test_trades for item in windows), mean(exposures))
        logger.warning("[V083 WF TRANSFER RESULT] strategy=%s windows=%d transfer_matches=%d transfer_match_pct=%.2f mean_oos_selection_gap=%.4f max_oos_selection_gap=%.4f", strategy, count, transfer_matches, transfer_matches / count * 100.0, mean(transfer_gaps) if transfer_gaps else 0.0, max(transfer_gaps) if transfer_gaps else 0.0)
        for criterion in criterion_matches:
            gaps = criterion_gaps[criterion]
            logger.warning("[V083 WF SELECTION RESULT] strategy=%s criterion=%s transfer_matches=%d transfer_match_pct=%.2f mean_oos_selection_gap=%.4f max_oos_selection_gap=%.4f", strategy, criterion, criterion_matches[criterion], criterion_matches[criterion] / count * 100.0, mean(gaps) if gaps else 0.0, max(gaps) if gaps else 0.0)
        logger.warning("[V083 WF RESULT] strategy=%s windows=%d mean_return=%.4f median_return=%.4f std_return=%.4f worst_return=%.4f best_return=%.4f mean_dd=%.4f mean_sharpe=%.4f positive=%d/%d risk_ok=%d/%d positive_sharpe=%d/%d return_consistency=%.2f risk_consistency=%.2f sharpe_consistency=%.2f parameter_stability=%.2f robustness=%.2f", strategy, count, result.mean_test_return_pct, result.median_test_return_pct, result.std_test_return_pct, result.worst_test_return_pct, result.best_test_return_pct, result.mean_test_drawdown_pct, result.mean_test_sharpe, result.positive_return_windows, count, result.risk_ok_windows, count, result.positive_sharpe_windows, count, result.return_consistency_pct, result.risk_consistency_pct, result.sharpe_consistency_pct, result.parameter_stability.stability_pct, result.robustness_score)
        return result

    @staticmethod
    def _empty(strategy: str) -> RobustWalkForwardResult:
        return RobustWalkForwardResult(strategy, (), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, ParameterStability(0, 0, 0.0, ()))


__all__ = ["ROBUST_WF_VERSION", "WalkForwardWindowResult", "ParameterStability", "RobustWalkForwardResult", "RobustWalkForwardService"]