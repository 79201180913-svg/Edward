from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import EventObservationV086
from edward.services.trading_rule_builder_v088 import TradingRuleV088


@dataclass(frozen=True, slots=True)
class EventTradeV088:
    event_index: int
    entry_index: int
    exit_index: int
    direction: str
    entry_price: float
    exit_price: float
    return_pct: float


@dataclass(frozen=True, slots=True)
class EventBacktestResultV088:
    ticker: str
    hypothesis: str
    horizon: int
    trades: tuple[EventTradeV088, ...]
    total_return_pct: float
    mean_trade_return_pct: float
    win_rate_pct: float


class EventBacktestV088:
    """Executable event backtest with explicit look-ahead-safe timing.

    An event is observable only after its source candle closes. Therefore the
    EVENT_CLOSE rule enters at the following candle's open, never at the event
    candle close. The exit is the close at event_index + horizon, matching the
    research horizon while making execution timing explicit.
    """

    @staticmethod
    def _direction_sign(direction: str) -> int:
        normalized = direction.strip().lower()
        if normalized in {"positive", "long", "up"}:
            return 1
        if normalized in {"negative", "short", "down"}:
            return -1
        raise ValueError(f"Unsupported trading path direction: {direction}")

    @classmethod
    def run(
        cls,
        candles: Sequence[Candle],
        observations: Sequence[EventObservationV086],
        rule: TradingRuleV088,
    ) -> EventBacktestResultV088:
        trades: list[EventTradeV088] = []
        sign = cls._direction_sign(rule.direction)
        for observation in observations:
            if observation.hypothesis != rule.hypothesis:
                continue
            event_index = observation.index
            entry_index = event_index + 1
            exit_index = event_index + rule.horizon
            if event_index < 0 or entry_index >= len(candles) or exit_index >= len(candles):
                continue
            entry_price = float(candles[entry_index].open)
            exit_price = float(candles[exit_index].close)
            if entry_price <= 0:
                continue
            raw_return = exit_price / entry_price - 1.0
            trade_return = raw_return * sign
            trades.append(
                EventTradeV088(
                    event_index=event_index,
                    entry_index=entry_index,
                    exit_index=exit_index,
                    direction=rule.direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    return_pct=trade_return * 100.0,
                )
            )

        compounded = 1.0
        for trade in trades:
            compounded *= 1.0 + trade.return_pct / 100.0
        mean_return = sum(t.return_pct for t in trades) / len(trades) if trades else 0.0
        wins = sum(1 for t in trades if t.return_pct > 0)
        return EventBacktestResultV088(
            ticker=rule.ticker,
            hypothesis=rule.hypothesis,
            horizon=rule.horizon,
            trades=tuple(trades),
            total_return_pct=(compounded - 1.0) * 100.0,
            mean_trade_return_pct=mean_return,
            win_rate_pct=(wins / len(trades) * 100.0) if trades else 0.0,
        )


__all__ = ["EventTradeV088", "EventBacktestResultV088", "EventBacktestV088"]
