from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import mean, median, pstdev
from typing import Any, Callable, Iterable, Sequence

from edward.services.analysis_service import Candle


RESEARCH_ENGINE_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class TradingCostModel:
    """Research-only transaction cost model.

    All rates are expressed in percent of notional. ``slippage_pct`` is charged
    on both entry and exit and therefore represents adverse execution on each leg.
    """

    commission_pct: float = 0.0
    spread_pct: float = 0.0
    slippage_pct: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("commission_pct", self.commission_pct),
            ("spread_pct", self.spread_pct),
            ("slippage_pct", self.slippage_pct),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0")

    @property
    def round_trip_pct(self) -> float:
        return 2.0 * (self.commission_pct + self.spread_pct / 2.0 + self.slippage_pct)


@dataclass(frozen=True, slots=True)
class BacktestTradeV08:
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_price: float
    exit_price: float
    gross_return_pct: float
    costs_pct: float
    net_return_pct: float
    holding_bars: int


@dataclass(frozen=True, slots=True)
class BacktestResultV08:
    strategy: str
    parameters: dict[str, Any]
    gross_return_pct: float
    net_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    calmar: float
    win_rate_pct: float
    profit_factor: float
    average_win_pct: float
    average_loss_pct: float
    trades: int
    turnover: float
    exposure_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    trades_detail: tuple[BacktestTradeV08, ...]
    equity_curve: tuple[float, ...]
    data_from: datetime | None
    data_to: datetime | None
    cost_model: TradingCostModel
    version: str = RESEARCH_ENGINE_VERSION


class ResearchEngineV08:
    """Research-grade long-only backtest with explicit execution assumptions.

    The engine deliberately operates on a signal callback so the existing
    strategy layer can remain unchanged while v0.8 research semantics evolve.
    A signal observed on bar ``i`` is executed at bar ``i + 1`` open.
    """

    @staticmethod
    def _returns(values: Sequence[float]) -> list[float]:
        return [current / previous - 1.0 for previous, current in zip(values, values[1:]) if previous]

    @staticmethod
    def _max_drawdown(equity: Sequence[float]) -> float:
        peak = equity[0] if equity else 1.0
        maximum = 0.0
        for value in equity:
            peak = max(peak, value)
            if peak:
                maximum = max(maximum, (peak - value) / peak)
        return maximum

    @staticmethod
    def _sharpe(returns: Sequence[float]) -> float:
        if len(returns) < 2:
            return 0.0
        deviation = pstdev(returns)
        return mean(returns) / deviation * sqrt(252.0) if deviation else 0.0

    @staticmethod
    def _sortino(returns: Sequence[float]) -> float:
        if not returns:
            return 0.0
        downside = [min(0.0, value) for value in returns]
        downside_deviation = sqrt(mean(value * value for value in downside))
        return mean(returns) / downside_deviation * sqrt(252.0) if downside_deviation else 0.0

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        if denominator == 0.0:
            return float("inf") if numerator > 0 else 0.0
        return numerator / denominator

    @classmethod
    def run(
        cls,
        candles: Iterable[Candle],
        strategy: str,
        parameters: dict[str, Any],
        signal_fn: Callable[[str, Sequence[Candle], dict[str, Any], int], bool],
        *,
        cost_model: TradingCostModel | None = None,
    ) -> BacktestResultV08:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        costs = cost_model or TradingCostModel()
        if len(ordered) < 3:
            return BacktestResultV08(
                strategy, dict(parameters), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, (),
                (1.0,), ordered[0].timestamp if ordered else None,
                ordered[-1].timestamp if ordered else None, costs,
            )

        equity = [1.0]
        trades: list[BacktestTradeV08] = []
        in_position = False
        entry_index = -1
        entry_price = 0.0
        gross_exposure_bars = 0
        turnover = 0.0

        for signal_index in range(len(ordered) - 1):
            signal = bool(signal_fn(strategy, ordered, parameters, signal_index))
            if not in_position and signal:
                entry_index = signal_index + 1
                raw_open = float(ordered[entry_index].open)
                entry_price = raw_open * (1.0 + costs.spread_pct / 200.0 + costs.slippage_pct / 100.0)
                in_position = True
                turnover += 1.0
                continue

            if in_position:
                gross_exposure_bars += 1
                bar_return = ordered[signal_index + 1].close / ordered[signal_index].open - 1.0 if ordered[signal_index].open else 0.0
                equity.append(equity[-1] * (1.0 + bar_return))

            if in_position and not signal:
                exit_index = signal_index + 1
                raw_close = float(ordered[exit_index].open)
                exit_price = raw_close * (1.0 - costs.spread_pct / 200.0 - costs.slippage_pct / 100.0)
                gross = exit_price / entry_price - 1.0 if entry_price else 0.0
                net = gross - 2.0 * costs.commission_pct / 100.0
                trades.append(
                    BacktestTradeV08(
                        entry_timestamp=ordered[entry_index].timestamp,
                        exit_timestamp=ordered[exit_index].timestamp,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        gross_return_pct=gross * 100.0,
                        costs_pct=(gross - net) * 100.0,
                        net_return_pct=net * 100.0,
                        holding_bars=max(1, exit_index - entry_index),
                    )
                )
                turnover += 1.0
                in_position = False
                entry_index = -1
                entry_price = 0.0

        if in_position and entry_index >= 0:
            exit_index = len(ordered) - 1
            raw_close = float(ordered[exit_index].close)
            exit_price = raw_close * (1.0 - costs.spread_pct / 200.0 - costs.slippage_pct / 100.0)
            gross = exit_price / entry_price - 1.0 if entry_price else 0.0
            net = gross - 2.0 * costs.commission_pct / 100.0
            trades.append(
                BacktestTradeV08(
                    entry_timestamp=ordered[entry_index].timestamp,
                    exit_timestamp=ordered[exit_index].timestamp,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_return_pct=gross * 100.0,
                    costs_pct=(gross - net) * 100.0,
                    net_return_pct=net * 100.0,
                    holding_bars=max(1, exit_index - entry_index),
                )
            )
            turnover += 1.0

        # Rebuild the equity curve from the same executed positions and costs.
        equity = [1.0]
        trade_by_exit = {trade.exit_timestamp: trade for trade in trades}
        active_trade: BacktestTradeV08 | None = None
        for index in range(1, len(ordered)):
            current = ordered[index]
            if active_trade is None:
                entered = next((trade for trade in trades if trade.entry_timestamp == current.timestamp), None)
                if entered is not None:
                    active_trade = entered
            growth = 0.0
            if active_trade is not None and ordered[index - 1].close:
                growth = current.close / ordered[index - 1].close - 1.0
                if current.timestamp == active_trade.exit_timestamp:
                    growth = active_trade.net_return_pct / 100.0 / max(1e-12, (active_trade.exit_price / active_trade.entry_price - 1.0) + 1.0) if False else growth
            equity.append(equity[-1] * (1.0 + growth) if active_trade is not None else equity[-1])
            if active_trade is not None and current.timestamp == active_trade.exit_timestamp:
                equity[-1] = equity[-2] * (1.0 + active_trade.net_return_pct / 100.0)
                active_trade = None

        net_return = equity[-1] - 1.0
        benchmark = ordered[-1].close / ordered[0].close - 1.0 if ordered[0].close else 0.0
        daily_strategy_returns = cls._returns(equity)
        dd = cls._max_drawdown(equity)
        sharpe = cls._sharpe(daily_strategy_returns)
        sortino = cls._sortino(daily_strategy_returns)
        annualized_return = net_return
        calmar = annualized_return / dd if dd else (float("inf") if annualized_return > 0 else 0.0)
        wins = [trade.net_return_pct for trade in trades if trade.net_return_pct > 0]
        losses = [abs(trade.net_return_pct) for trade in trades if trade.net_return_pct < 0]
        profit_factor = cls._safe_ratio(sum(wins), sum(losses))
        exposure_pct = gross_exposure_bars / max(1, len(ordered) - 1) * 100.0

        return BacktestResultV08(
            strategy=strategy,
            parameters=dict(parameters),
            gross_return_pct=sum(trade.gross_return_pct for trade in trades),
            net_return_pct=net_return * 100.0,
            max_drawdown_pct=dd * 100.0,
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            win_rate_pct=len(wins) / len(trades) * 100.0 if trades else 0.0,
            profit_factor=profit_factor,
            average_win_pct=mean(wins) if wins else 0.0,
            average_loss_pct=-mean(losses) if losses else 0.0,
            trades=len(trades),
            turnover=turnover,
            exposure_pct=exposure_pct,
            benchmark_return_pct=benchmark * 100.0,
            excess_return_pct=(net_return - benchmark) * 100.0,
            trades_detail=tuple(trades),
            equity_curve=tuple(equity),
            data_from=ordered[0].timestamp,
            data_to=ordered[-1].timestamp,
            cost_model=costs,
        )


@dataclass(frozen=True, slots=True)
class WalkForwardWindowV08:
    start: datetime
    train_end: datetime
    test_end: datetime
    selected_parameters: dict[str, Any]
    train_score: float
    test_result: BacktestResultV08


@dataclass(frozen=True, slots=True)
class RobustWalkForwardResultV08:
    strategy: str
    windows: tuple[WalkForwardWindowV08, ...]
    mean_test_return_pct: float
    median_test_return_pct: float
    mean_test_drawdown_pct: float
    mean_test_sharpe: float
    positive_return_consistency_pct: float
    risk_ok_consistency_pct: float
    positive_sharpe_consistency_pct: float
    parameter_stability_pct: float
    worst_window_return_pct: float
    best_window_return_pct: float
    robustness_score: float
    version: str = RESEARCH_ENGINE_VERSION


class RobustWalkForwardServiceV08:
    """Rolling walk-forward with parameter stability and dispersion metrics."""

    def __init__(self, *, min_train_size: int = 240, test_size: int = 60, step_size: int = 60, max_drawdown_pct: float = 25.0) -> None:
        if min_train_size < 10 or test_size < 1 or step_size < 1:
            raise ValueError("Invalid walk-forward window configuration")
        self.min_train_size = min_train_size
        self.test_size = test_size
        self.step_size = step_size
        self.max_drawdown_pct = max_drawdown_pct

    def run(
        self,
        candles: Iterable[Candle],
        strategy: str,
        parameter_grid: Iterable[dict[str, Any]],
        signal_fn: Callable[[str, Sequence[Candle], dict[str, Any], int], bool],
        *,
        cost_model: TradingCostModel | None = None,
    ) -> RobustWalkForwardResultV08:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        grid = [dict(item) for item in parameter_grid]
        if not grid:
            raise ValueError("parameter_grid must not be empty")
        windows: list[WalkForwardWindowV08] = []
        start = 0
        while start + self.min_train_size + self.test_size <= len(ordered):
            train = ordered[start:start + self.min_train_size]
            test = ordered[start + self.min_train_size:start + self.min_train_size + self.test_size]
            train_results = [ResearchEngineV08.run(train, strategy, params, signal_fn, cost_model=cost_model) for params in grid]
            best = max(train_results, key=lambda item: (item.net_return_pct, item.sharpe, -item.max_drawdown_pct))
            tested = ResearchEngineV08.run(test, strategy, best.parameters, signal_fn, cost_model=cost_model)
            windows.append(
                WalkForwardWindowV08(
                    start=train[0].timestamp,
                    train_end=train[-1].timestamp,
                    test_end=test[-1].timestamp,
                    selected_parameters=dict(best.parameters),
                    train_score=best.net_return_pct,
                    test_result=tested,
                )
            )
            start += self.step_size

        returns = [window.test_result.net_return_pct for window in windows]
        drawdowns = [window.test_result.max_drawdown_pct for window in windows]
        sharpes = [window.test_result.sharpe for window in windows]
        positive = [value > 0.0 for value in returns]
        risk_ok = [value <= self.max_drawdown_pct for value in drawdowns]
        positive_sharpe = [value > 0.0 for value in sharpes]
        unique_parameter_sets = {tuple(sorted(window.selected_parameters.items())) for window in windows}
        parameter_stability = 100.0 if len(unique_parameter_sets) <= 1 else max(0.0, 100.0 * (1.0 - (len(unique_parameter_sets) - 1) / max(1, len(windows) - 1)))
        robustness_score = round(
            (mean(returns) if returns else 0.0) * 2.0
            + (sum(positive) / len(positive) * 100.0 if positive else 0.0) * 0.35
            + (sum(risk_ok) / len(risk_ok) * 100.0 if risk_ok else 0.0) * 0.25
            + (sum(positive_sharpe) / len(positive_sharpe) * 100.0 if positive_sharpe else 0.0) * 0.20
            + parameter_stability * 0.20,
            2,
        )
        return RobustWalkForwardResultV08(
            strategy=strategy,
            windows=tuple(windows),
            mean_test_return_pct=mean(returns) if returns else 0.0,
            median_test_return_pct=median(returns) if returns else 0.0,
            mean_test_drawdown_pct=mean(drawdowns) if drawdowns else 0.0,
            mean_test_sharpe=mean(sharpes) if sharpes else 0.0,
            positive_return_consistency_pct=sum(positive) / len(positive) * 100.0 if positive else 0.0,
            risk_ok_consistency_pct=sum(risk_ok) / len(risk_ok) * 100.0 if risk_ok else 0.0,
            positive_sharpe_consistency_pct=sum(positive_sharpe) / len(positive_sharpe) * 100.0 if positive_sharpe else 0.0,
            parameter_stability_pct=parameter_stability,
            worst_window_return_pct=min(returns) if returns else 0.0,
            best_window_return_pct=max(returns) if returns else 0.0,
            robustness_score=robustness_score,
        )


class PointInTimeIntegrityV08:
    """Validate that model inputs do not extend beyond the decision origin."""

    @staticmethod
    def candles_at_origin(candles: Iterable[Candle], origin_timestamp: datetime) -> list[Candle]:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        return [item for item in ordered if item.timestamp <= origin_timestamp]

    @classmethod
    def assert_no_future_data(cls, candles: Iterable[Candle], origin_timestamp: datetime) -> None:
        future = [item.timestamp for item in candles if item.timestamp > origin_timestamp]
        if future:
            raise ValueError(
                f"POINT_IN_TIME_VIOLATION: {len(future)} observations after origin {origin_timestamp.isoformat()}"
            )

    @classmethod
    def validate_window(cls, train: Sequence[Candle], validation: Sequence[Candle], origin_timestamp: datetime) -> None:
        cls.assert_no_future_data(train, origin_timestamp)
        cls.assert_no_future_data(validation, origin_timestamp)
        if train and train[-1].timestamp > origin_timestamp:
            raise ValueError("TRAIN_DATA_AFTER_ORIGIN")
        if validation and validation[0].timestamp <= origin_timestamp:
            raise ValueError("VALIDATION_DATA_LEAKAGE_AT_ORIGIN")


__all__ = [
    "RESEARCH_ENGINE_VERSION",
    "TradingCostModel",
    "BacktestTradeV08",
    "BacktestResultV08",
    "ResearchEngineV08",
    "WalkForwardWindowV08",
    "RobustWalkForwardResultV08",
    "RobustWalkForwardServiceV08",
    "PointInTimeIntegrityV08",
]
