from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Any, Callable, Iterable, Sequence

from edward.services.analysis_service import Candle
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult, ResearchBacktestService


ROBUST_WF_VERSION = "0.8.0"


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
        max_drawdown_pct: float | None = None,
    ) -> RobustWalkForwardResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if train_size < 2 or test_size < 1:
            raise ValueError("train_size must be >= 2 and test_size must be >= 1")
        if not parameter_grid:
            raise ValueError("parameter_grid cannot be empty")

        windows: list[WalkForwardWindowResult] = []
        start = 0
        while start + train_size + test_size <= len(ordered):
            train = ordered[start:start + train_size]
            test = ordered[start + train_size:start + train_size + test_size]
            candidates: list[tuple[dict[str, Any], ResearchBacktestResult]] = []
            for params in parameter_grid:
                candidates.append((dict(params), ResearchBacktestService.run(
                    candles=train,
                    strategy=strategy,
                    parameters=params,
                    signal_fn=signal_factory(strategy, params),
                    costs=costs,
                )))
            selected_params, train_result = max(
                candidates,
                key=lambda item: (item[1].excess_return_pct, item[1].sharpe, -item[1].max_drawdown_pct),
            )
            test_result = ResearchBacktestService.run(
                candles=test,
                strategy=strategy,
                parameters=selected_params,
                signal_fn=signal_factory(strategy, selected_params),
                costs=costs,
            )
            window_index = len(windows)
            windows.append(WalkForwardWindowResult(
                window_index, train[0].timestamp, train[-1].timestamp,
                test[0].timestamp, test[-1].timestamp, dict(selected_params),
                train_result.excess_return_pct, test_result.net_return_pct,
                test_result.benchmark_return_pct, test_result.excess_return_pct,
                test_result.max_drawdown_pct, test_result.sharpe,
                test_result.sortino, test_result.trades,
            ))
            start += test_size

        if not windows:
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
        robustness = round(
            return_consistency * 0.35 + risk_consistency * 0.20 +
            sharpe_consistency * 0.15 + stability.stability_pct * 0.15 +
            performance_consistency * 0.15,
            2,
        )
        return RobustWalkForwardResult(
            strategy=strategy, windows=tuple(windows),
            mean_test_return_pct=mean(returns), median_test_return_pct=median(returns),
            std_test_return_pct=pstdev(returns) if len(returns) > 1 else 0.0,
            worst_test_return_pct=min(returns), best_test_return_pct=max(returns),
            mean_test_drawdown_pct=mean(drawdowns), mean_test_sharpe=mean(sharpes),
            positive_return_windows=positive, risk_ok_windows=risk_ok,
            positive_sharpe_windows=positive_sharpe,
            return_consistency_pct=return_consistency,
            risk_consistency_pct=risk_consistency,
            sharpe_consistency_pct=sharpe_consistency,
            robustness_score=robustness, parameter_stability=stability,
        )

    @staticmethod
    def _empty(strategy: str) -> RobustWalkForwardResult:
        return RobustWalkForwardResult(
            strategy, (), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0, 0, 0, 0.0, 0.0, 0.0, 0.0,
            ParameterStability(0, 0, 0.0, ()),
        )


__all__ = ["ROBUST_WF_VERSION", "WalkForwardWindowResult", "ParameterStability", "RobustWalkForwardResult", "RobustWalkForwardService"]
