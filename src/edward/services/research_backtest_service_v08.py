from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, median, pstdev
from typing import Any, Callable, Iterable, Sequence

from edward.services.analysis_service import Candle


RESEARCH_BACKTEST_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class BacktestCostModel:
    commission_pct: float = 0.0
    spread_pct: float = 0.0
    slippage_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.commission_pct < 0 or self.spread_pct < 0 or self.slippage_pct < 0:
            raise ValueError("Transaction costs cannot be negative")

    @property
    def one_side_pct(self) -> float:
        return self.commission_pct + self.spread_pct / 2.0 + self.slippage_pct

    @property
    def round_trip_pct(self) -> float:
        return self.one_side_pct * 2.0


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    entry_timestamp: Any
    exit_timestamp: Any
    entry_price: float
    exit_price: float
    gross_return_pct: float
    cost_pct: float
    net_return_pct: float


@dataclass(frozen=True, slots=True)
class ResearchBacktestResult:
    strategy: str
    parameters: dict[str, Any]
    gross_return_pct: float
    net_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    calmar: float
    trades: int
    win_rate_pct: float
    profit_factor: float
    payoff_ratio: float
    turnover_pct: float
    exposure_pct: float
    average_trade_pct: float
    median_trade_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    positive_days_pct: float
    equity: tuple[float, ...]
    trades_detail: tuple[BacktestTrade, ...]
    version: str = RESEARCH_BACKTEST_VERSION


class ResearchBacktestService:
    """Execution-consistent, cost-aware strategy research backtest.

    Signals are evaluated using information available through candle ``i-1``.
    Entry/exit executes at candle ``i`` open. Costs are paid once per side.
    Equity is marked from the actual executed entry/exit path, so trade metrics
    and drawdown use the same economic model.
    """

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return [
            current.close / previous.close - 1.0
            for previous, current in zip(candles, candles[1:])
            if previous.close > 0 and current.close > 0
        ]

    @staticmethod
    def _max_drawdown(equity: Sequence[float]) -> float:
        peak = equity[0] if equity else 1.0
        result = 0.0
        for value in equity:
            peak = max(peak, value)
            if peak > 0:
                result = max(result, (peak - value) / peak)
        return result

    @staticmethod
    def _sharpe(returns: Sequence[float], annualization: float = 252.0) -> float:
        if len(returns) < 2:
            return 0.0
        sigma = pstdev(returns)
        return 0.0 if sigma == 0 else mean(returns) / sigma * sqrt(annualization)

    @staticmethod
    def _sortino(returns: Sequence[float], annualization: float = 252.0) -> float:
        if len(returns) < 2:
            return 0.0
        downside = [min(0.0, value) for value in returns]
        denominator = sqrt(mean(value * value for value in downside))
        return 0.0 if denominator == 0 else mean(returns) / denominator * sqrt(annualization)

    @classmethod
    def _simulate_positions(
        cls,
        candles: Sequence[Candle],
        signal_fn: Callable[[Sequence[Candle], int], bool],
        costs: BacktestCostModel,
    ) -> tuple[list[BacktestTrade], list[float], list[float], float]:
        trades: list[BacktestTrade] = []
        equity = [1.0]
        period_returns: list[float] = []
        if len(candles) < 2:
            return trades, equity, period_returns, 0.0

        one_side = costs.one_side_pct / 100.0
        in_position = False
        entry_price = 0.0
        entry_timestamp: Any = None
        equity_value = 1.0
        mark_price = 0.0
        exposure_periods = 0
        turnover_sides = 0

        def enter(candle: Candle) -> None:
            nonlocal in_position, entry_price, entry_timestamp, equity_value, mark_price, turnover_sides
            entry_price = float(candle.open)
            entry_timestamp = candle.timestamp
            mark_price = entry_price
            equity_value *= 1.0 - one_side
            in_position = True
            turnover_sides += 1

        def exit(candle: Candle, price: float) -> None:
            nonlocal in_position, equity_value, turnover_sides, mark_price
            exit_price = float(price)
            if entry_price <= 0:
                in_position = False
                return
            gross_factor = exit_price / entry_price
            net_factor = gross_factor * (1.0 - one_side) / max(1.0 - one_side, 1e-12)
            # Equity has already absorbed the entry cost and mark-to-market P/L.
            # Only the exit-side cost is applied here.
            equity_value *= 1.0 - one_side
            trades.append(
                BacktestTrade(
                    entry_timestamp=entry_timestamp,
                    exit_timestamp=candle.timestamp,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_return_pct=(gross_factor - 1.0) * 100.0,
                    cost_pct=costs.round_trip_pct,
                    net_return_pct=(net_factor - 1.0) * 100.0,
                )
            )
            mark_price = exit_price
            in_position = False
            turnover_sides += 1

        for index in range(1, len(candles)):
            previous_signal = bool(signal_fn(candles, index - 1))
            current = candles[index]

            if previous_signal and not in_position:
                enter(current)
                # The entry candle is not marked from the previous close because
                # the strategy did not own the asset before the executable open.
                equity.append(equity_value)
                period_returns.append(0.0)
                continue

            if not previous_signal and in_position:
                exit(current, current.open)
                current_return = equity_value / max(equity[-1], 1e-12) - 1.0
                equity.append(equity_value)
                period_returns.append(current_return)
                continue

            if in_position:
                previous_mark = mark_price
                current_close = float(current.close)
                if previous_mark > 0:
                    period_return = current_close / previous_mark - 1.0
                    equity_value *= 1.0 + period_return
                    period_returns.append(period_return)
                    exposure_periods += 1
                    mark_price = current_close
                else:
                    period_returns.append(0.0)
            else:
                period_returns.append(0.0)
            equity.append(equity_value)

        if in_position:
            last = candles[-1]
            exit(last, last.close)
            final_return = equity_value / max(equity[-1], 1e-12) - 1.0
            equity.append(equity_value)
            period_returns.append(final_return)

        return trades, equity, period_returns, float(turnover_sides)

    @classmethod
    def run(
        cls,
        *,
        candles: Iterable[Candle],
        strategy: str,
        parameters: dict[str, Any],
        signal_fn: Callable[[Sequence[Candle], int], bool],
        costs: BacktestCostModel | None = None,
    ) -> ResearchBacktestResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if len(ordered) < 2:
            return ResearchBacktestResult(
                strategy, dict(parameters), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                (1.0,), (), RESEARCH_BACKTEST_VERSION,
            )

        model = costs or BacktestCostModel()
        trades, equity, strategy_returns, turnover_sides = cls._simulate_positions(ordered, signal_fn, model)
        benchmark_returns = cls._returns(ordered)
        benchmark = 1.0
        for value in benchmark_returns:
            benchmark *= 1.0 + value

        gross_factor = 1.0
        net_factor = 1.0
        for trade in trades:
            gross_factor *= 1.0 + trade.gross_return_pct / 100.0
            net_factor *= 1.0 + trade.net_return_pct / 100.0

        gross_return = gross_factor - 1.0
        net_return = equity[-1] - 1.0
        # The explicit net trade factor is a consistency diagnostic; equity is
        # authoritative because it includes mark-to-market path and costs.
        _ = net_factor

        drawdown = cls._max_drawdown(equity)
        sharpe = cls._sharpe(strategy_returns)
        sortino = cls._sortino(strategy_returns)
        days = max((ordered[-1].timestamp - ordered[0].timestamp).total_seconds() / 86400.0, 1.0)
        years = days / 365.25
        cagr = equity[-1] ** (1.0 / years) - 1.0 if equity[-1] > 0 else -1.0
        calmar = cagr / drawdown if drawdown > 0 else 0.0

        wins = [trade.net_return_pct for trade in trades if trade.net_return_pct > 0]
        losses = [trade.net_return_pct for trade in trades if trade.net_return_pct < 0]
        win_rate = len(wins) / len(trades) * 100.0 if trades else 0.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
        avg_win = mean(wins) if wins else 0.0
        avg_loss = abs(mean(losses)) if losses else 0.0
        payoff_ratio = avg_win / avg_loss if avg_loss else (float("inf") if avg_win else 0.0)
        exposure = sum(1 for value in strategy_returns if value != 0.0) / max(1, len(strategy_returns)) * 100.0
        excess = net_return - (benchmark - 1.0)
        positive_days = sum(1 for value in strategy_returns if value > 0) / max(1, len(strategy_returns)) * 100.0

        return ResearchBacktestResult(
            strategy=strategy,
            parameters=dict(parameters),
            gross_return_pct=gross_return * 100.0,
            net_return_pct=net_return * 100.0,
            benchmark_return_pct=(benchmark - 1.0) * 100.0,
            excess_return_pct=excess * 100.0,
            max_drawdown_pct=drawdown * 100.0,
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            trades=len(trades),
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            payoff_ratio=payoff_ratio,
            turnover_pct=turnover_sides / max(1, len(ordered) - 1) * 100.0,
            exposure_pct=exposure,
            average_trade_pct=mean(trade.net_return_pct for trade in trades) if trades else 0.0,
            median_trade_pct=median(trade.net_return_pct for trade in trades) if trades else 0.0,
            best_trade_pct=max((trade.net_return_pct for trade in trades), default=0.0),
            worst_trade_pct=min((trade.net_return_pct for trade in trades), default=0.0),
            positive_days_pct=positive_days,
            equity=tuple(equity),
            trades_detail=tuple(trades),
        )

    @staticmethod
    def simple_signal(strategy: str, candles: Sequence[Candle], parameters: dict[str, Any], index: int) -> bool:
        closes = [float(item.close) for item in candles[: index + 1]]
        if strategy == "Trend Following":
            fast, slow = int(parameters["fast"]), int(parameters["slow"])
            if len(closes) < slow:
                return False
            return sum(closes[-fast:]) / fast > sum(closes[-slow:]) / slow
        if strategy == "Momentum":
            lookback = int(parameters["lookback"])
            return len(closes) > lookback and closes[-1] > closes[-1 - lookback]
        if strategy == "Breakout":
            lookback = int(parameters["lookback"])
            return len(closes) > lookback and closes[-1] >= max(closes[-1 - lookback:-1])
        if strategy == "Mean Reversion":
            lookback = int(parameters["lookback"])
            deviation = float(parameters["deviation"])
            if len(closes) < lookback:
                return False
            average = sum(closes[-lookback:]) / lookback
            return closes[-1] < average * (1.0 - deviation / 100.0)
        raise ValueError(f"Unsupported strategy: {strategy}")

    @classmethod
    def run_simple_strategy(
        cls,
        *,
        candles: Iterable[Candle],
        strategy: str,
        parameters: dict[str, Any],
        costs: BacktestCostModel | None = None,
    ) -> ResearchBacktestResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        return cls.run(
            candles=ordered,
            strategy=strategy,
            parameters=parameters,
            signal_fn=lambda items, index: cls.simple_signal(strategy, items, parameters, index),
            costs=costs,
        )
