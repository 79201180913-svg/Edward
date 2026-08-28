from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from math import inf, sqrt
from statistics import mean, pstdev
from typing import Callable, Sequence

from edward.services.analysis_service import Candle


RESEARCH_BACKTEST_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class BacktestCostModel:
    """Per-side research trading costs expressed in basis points."""

    commission_bps: float = 0.0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0

    def __post_init__(self) -> None:
        if self.commission_bps < 0 or self.spread_bps < 0 or self.slippage_bps < 0:
            raise ValueError("Backtest costs cannot be negative")

    @property
    def per_side_rate(self) -> float:
        # The bid/ask spread is paid across the round trip, so half is assigned
        # to each side. Commission and slippage are charged on each side.
        return (
            self.commission_bps / 10_000.0
            + self.spread_bps / 20_000.0
            + self.slippage_bps / 10_000.0
        )


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    entry_timestamp: object
    exit_timestamp: object
    entry_price: float
    exit_price: float
    gross_return_pct: float
    net_return_pct: float
    cost_pct: float


@dataclass(frozen=True, slots=True)
class BacktestResult:
    strategy: str
    gross_return_pct: float
    net_return_pct: float
    total_cost_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    calmar: float
    benchmark_return_pct: float
    excess_return_pct: float
    trades: int
    win_rate_pct: float
    profit_factor: float
    payoff_ratio: float
    turnover: float
    exposure_pct: float
    trade_returns_pct: tuple[float, ...]
    equity_curve: tuple[float, ...]
    version: str = RESEARCH_BACKTEST_VERSION


class ResearchBacktestService:
    """Long-only, point-in-time-safe research backtest.

    A signal for candle ``i`` is assumed known at that candle's close and is
    executed at candle ``i + 1`` open. Equity is marked to every close, so gaps
    between signal/entry and exit are represented consistently.
    """

    def __init__(
        self,
        *,
        cost_model: BacktestCostModel | None = None,
        periods_per_year: float = 252.0,
    ) -> None:
        if periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive")
        self.cost_model = cost_model or BacktestCostModel()
        self.periods_per_year = periods_per_year

    @staticmethod
    def _max_drawdown(equity: Sequence[float]) -> float:
        if not equity:
            return 0.0
        peak = equity[0]
        maximum = 0.0
        for value in equity:
            peak = max(peak, value)
            if peak > 0:
                maximum = max(maximum, (peak - value) / peak)
        return maximum

    @staticmethod
    def _period_returns(equity: Sequence[float]) -> list[float]:
        return [current / previous - 1.0 for previous, current in zip(equity, equity[1:]) if previous]

    def _sharpe(self, returns: Sequence[float]) -> float:
        if len(returns) < 2:
            return 0.0
        deviation = pstdev(returns)
        if deviation == 0:
            return 0.0
        return mean(returns) / deviation * sqrt(self.periods_per_year)

    def _sortino(self, returns: Sequence[float]) -> float:
        if not returns:
            return 0.0
        downside = [min(0.0, value) for value in returns]
        downside_deviation = sqrt(mean(value * value for value in downside))
        if downside_deviation == 0:
            return inf if mean(returns) > 0 else 0.0
        return mean(returns) / downside_deviation * sqrt(self.periods_per_year)

    @staticmethod
    def _annualized_return(initial: float, final: float, timestamps: Sequence[object]) -> float:
        if initial <= 0 or final <= 0 or len(timestamps) < 2:
            return 0.0
        first = timestamps[0]
        last = timestamps[-1]
        if not hasattr(first, "__sub__"):
            return 0.0
        elapsed = last - first
        days = max(float(getattr(elapsed, "total_seconds", lambda: 0.0)()) / 86_400.0, 1.0)
        years = days / 365.25
        if years <= 0:
            return 0.0
        return (final / initial) ** (1.0 / years) - 1.0

    def run(
        self,
        candles: Sequence[Candle],
        *,
        strategy: str,
        signal: Callable[[Sequence[Candle], int], bool],
    ) -> BacktestResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if len(ordered) < 3:
            return BacktestResult(strategy, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, (), (1.0,))

        cost_rate = self.cost_model.per_side_rate
        equity = 1.0
        gross_equity = 1.0
        curve = [equity]
        in_position = False
        entry_price = 0.0
        entry_gross_price = 0.0
        entry_timestamp = None
        trades: list[BacktestTrade] = []
        daily_exposure: list[float] = []
        traded_notional = 0.0

        for execution_index in range(1, len(ordered)):
            bar = ordered[execution_index]
            signal_index = execution_index - 1
            desired = bool(signal(ordered, signal_index))

            if desired and not in_position:
                entry_gross_price = float(bar.open)
                entry_price = entry_gross_price * (1.0 + cost_rate)
                entry_timestamp = bar.timestamp
                in_position = True
                traded_notional += 1.0
            elif not desired and in_position:
                exit_gross_price = float(bar.open)
                exit_price = exit_gross_price * (1.0 - cost_rate)
                gross_trade = exit_gross_price / entry_gross_price - 1.0 if entry_gross_price else 0.0
                net_trade = exit_price / entry_price - 1.0 if entry_price else 0.0
                cost_pct = gross_trade - net_trade
                trades.append(
                    BacktestTrade(
                        entry_timestamp,
                        bar.timestamp,
                        entry_gross_price,
                        exit_gross_price,
                        gross_trade * 100.0,
                        net_trade * 100.0,
                        cost_pct * 100.0,
                    )
                )
                equity *= max(0.0, exit_price / entry_price)
                gross_equity *= max(0.0, exit_gross_price / entry_gross_price)
                curve.append(equity)
                curve.append(equity)
                traded_notional += 1.0
                in_position = False
                entry_price = 0.0
                entry_gross_price = 0.0
                entry_timestamp = None
                daily_exposure.append(0.0)
                continue

            if in_position and bar.close > 0 and entry_price > 0:
                marked = bar.close / entry_price
                gross_marked = bar.close / entry_gross_price if entry_gross_price else 1.0
                current_equity = equity * marked
                current_gross_equity = gross_equity * gross_marked
                # equity/gross_equity are carried from the latest execution event;
                # marking from the original entry price is valid until the next event.
                curve.append(current_equity)
                curve[-1] = max(curve[-2], current_equity) if current_equity >= curve[-2] else current_equity
                gross_equity = max(gross_equity, current_gross_equity) if current_gross_equity >= gross_equity else current_gross_equity
                daily_exposure.append(1.0)
            else:
                curve.append(equity)
                daily_exposure.append(0.0)

        if in_position and entry_price > 0:
            bar = ordered[-1]
            exit_gross_price = float(bar.close)
            exit_price = exit_gross_price * (1.0 - cost_rate)
            gross_trade = exit_gross_price / entry_gross_price - 1.0
            net_trade = exit_price / entry_price - 1.0
            trades.append(
                BacktestTrade(
                    entry_timestamp,
                    bar.timestamp,
                    entry_gross_price,
                    exit_gross_price,
                    gross_trade * 100.0,
                    net_trade * 100.0,
                    (gross_trade - net_trade) * 100.0,
                )
            )
            curve.append(equity * max(0.0, exit_price / entry_price))
            traded_notional += 1.0
            daily_exposure.append(1.0)

        # Reconstruct a stable marked-to-market series from the resulting bars.
        # This series intentionally uses net execution prices and therefore differs
        # from the old AnalysisService equity approximation.
        stable_curve = [1.0]
        position = False
        units = 1.0
        entry_fill = 0.0
        for i in range(1, len(ordered)):
            if bool(signal(ordered, i - 1)) and not position:
                entry_fill = ordered[i].open * (1.0 + cost_rate)
                position = True
            elif not bool(signal(ordered, i - 1)) and position:
                exit_fill = ordered[i].open * (1.0 - cost_rate)
                if entry_fill > 0:
                    stable_curve.append(stable_curve[-1] * (exit_fill / entry_fill))
                else:
                    stable_curve.append(stable_curve[-1])
                position = False
                entry_fill = 0.0
            if position and entry_fill > 0:
                stable_curve.append(stable_curve[-1] * (ordered[i].close / entry_fill))
            elif not position and len(stable_curve) < i + 2:
                stable_curve.append(stable_curve[-1])

        # Guarantee enough observations for volatility metrics.
        if len(stable_curve) < 2:
            stable_curve.append(stable_curve[-1])

        period_returns = self._period_returns(stable_curve)
        max_dd = self._max_drawdown(stable_curve)
        net_return = stable_curve[-1] - 1.0
        gross_return = trades and _compound([trade.gross_return_pct / 100.0 + 1.0 for trade in trades]) - 1.0 or 0.0
        total_cost = max(0.0, gross_return - net_return)
        benchmark = ordered[-1].close / ordered[0].open - 1.0 if ordered[0].open else 0.0
        excess = net_return - benchmark
        wins = [trade.net_return_pct for trade in trades if trade.net_return_pct > 0]
        losses = [trade.net_return_pct for trade in trades if trade.net_return_pct < 0]
        profit_factor = sum(wins) / abs(sum(losses)) if losses else (inf if wins else 0.0)
        payoff = mean(wins) / abs(mean(losses)) if wins and losses else (inf if wins else 0.0)
        annual = self._annualized_return(1.0, stable_curve[-1], [item.timestamp for item in ordered])
        calmar = annual / max_dd if max_dd > 0 else (inf if annual > 0 else 0.0)
        exposure = mean(daily_exposure) * 100.0 if daily_exposure else 0.0

        return BacktestResult(
            strategy=strategy,
            gross_return_pct=round(gross_return * 100.0, 8),
            net_return_pct=round(net_return * 100.0, 8),
            total_cost_pct=round(total_cost * 100.0, 8),
            max_drawdown_pct=round(max_dd * 100.0, 8),
            sharpe=round(self._sharpe(period_returns), 8),
            sortino=round(self._sortino(period_returns), 8),
            calmar=round(calmar, 8),
            benchmark_return_pct=round(benchmark * 100.0, 8),
            excess_return_pct=round(excess * 100.0, 8),
            trades=len(trades),
            win_rate_pct=round(len(wins) / len(trades) * 100.0, 8) if trades else 0.0,
            profit_factor=round(profit_factor, 8) if profit_factor != inf else inf,
            payoff_ratio=round(payoff, 8) if payoff != inf else inf,
            turnover=round(traded_notional, 8),
            exposure_pct=round(exposure, 8),
            trade_returns_pct=tuple(round(item.net_return_pct, 8) for item in trades),
            equity_curve=tuple(round(item, 10) for item in stable_curve),
        )


def _compound(factors: Sequence[float]) -> float:
    result = 1.0
    for factor in factors:
        result *= factor
    return result


__all__ = [
    "RESEARCH_BACKTEST_VERSION",
    "BacktestCostModel",
    "BacktestTrade",
    "BacktestResult",
    "ResearchBacktestService",
]
