from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, median, pstdev
from typing import Callable, Iterable, Sequence, Any

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
    def round_trip_pct(self) -> float:
        return 2.0 * (self.commission_pct + self.spread_pct / 2.0 + self.slippage_pct)


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

    The signal is evaluated using information available at candle ``i-1``.
    Entry/exit occurs at candle ``i`` open, with costs applied at both sides.
    The equity curve is built from the same executed transactions and therefore
    represents the same economic model as the trade statistics.
    """

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return [
            current.close / previous.close - 1.0
            for previous, current in zip(candles, candles[1:])
            if previous.close > 0
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
        if not candles:
            return [], [1.0], [], 0.0

        trades: list[BacktestTrade] = []
        equity = [1.0]
        period_returns: list[float] = []
        in_position = False
        entry_price = 0.0
        entry_time = None
        equity_value = 1.0
        exposure_periods = 0
        turnover = 0.0

        entry_cost = (costs.commission_pct + costs.spread_pct / 2.0 + costs.slippage_pct) / 100.0
        exit_cost = entry_cost

        for index in range(1, len(candles)):
            signal = bool(signal_fn(candles, index - 1))
            current = candles[index]

            if signal and not in_position:
                entry_price = float(current.open) * (1.0 + entry_cost)
                entry_time = current.timestamp
                in_position = True
                turnover += 1.0
            elif not signal and in_position:
                raw_exit = float(current.open) * (1.0 - exit_cost)
                gross = raw_exit / entry_price - 1.0
                gross_before_cost = float(current.open) / float(candles[index if entry_time is not None else index].open) if False else 0.0
                net = gross
                trades.append(
                    BacktestTrade(
                        entry_timestamp=entry_time,
                        exit_timestamp=current.timestamp,
                        entry_price=entry_price,
                        exit_price=raw_exit,
                        gross_return_pct=(float(current.open) / max(entry_price, 1e-12) - 1.0) * 100.0,
                        cost_pct=costs.round_trip_pct,
                        net_return_pct=net * 100.0,
                    )
                )
                equity_value *= 1.0 + net
                equity.append(equity_value)
                period_returns.append(net)
                in_position = False
                turnover += 1.0
                continue

            if in_position:
                exposure_periods += 1
                period_return = float(current.close) / max(float(candles[index - 1].close), 1e-12) - 1.0
                equity_value *= 1.0 + period_return
                period_returns.append(period_return)
            else:
                period_returns.append(0.0)
            equity.append(equity_value)

        if in_position and entry_price:
            last = candles[-1]
            raw_exit = float(last.close) * (1.0 - exit_cost)
            gross = raw_exit / entry_price - 1.0
            net = gross
            trades.append(
                BacktestTrade(
                    entry_timestamp=entry_time,
                    exit_timestamp=last.timestamp,
                    entry_price=entry_price,
                    exit_price=raw_exit,
                    gross_return_pct=(float(last.close) / max(entry_price, 1e-12) - 1.0) * 100.0,
                    cost_pct=costs.round_trip_pct,
                    net_return_pct=net * 100.0,
                )
            )
            equity_value *= 1.0 + net
            equity.append(equity_value)
            period_returns.append(net)
            turnover += 1.0

        exposure_pct = exposure_periods / max(1, len(candles) - 1) * 100.0
        return trades, equity, period_returns, turnover

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
        trades, equity, strategy_returns, turnover_units = cls._simulate_positions(ordered, signal_fn, model)
        benchmark_returns = cls._returns(ordered)
        benchmark = 1.0
        for value in benchmark_returns:
            benchmark *= 1.0 + value

        gross_return = 0.0
        if trades:
            gross_return = 1.0
            for trade in trades:
                gross_return *= 1.0 + trade.gross_return_pct / 100.0
            gross_return -= 1.0
        net_return = equity[-1] - 1.0
        drawdown = cls._max_drawdown(equity)
        sharpe = cls._sharpe(strategy_returns)
        sortino = cls._sortino(strategy_returns)
        years = max((ordered[-1].timestamp - ordered[0].timestamp).total_seconds() / 86400.0 / 365.25, 1.0 / 365.25)
        cagr = (max(equity[-1], 0.0)) ** (1.0 / years) - 1.0 if equity[-1] > 0 else -1.0
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
        exposure = sum(1.0 for value in strategy_returns if value != 0.0) / max(1, len(strategy_returns)) * 100.0
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
            turnover_pct=turnover_units / max(1, len(ordered) - 1) * 100.0,
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
