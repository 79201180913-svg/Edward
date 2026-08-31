from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TradingCostModelV088:
    commission_pct_per_side: float = 0.0
    slippage_pct_per_side: float = 0.0
    spread_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.commission_pct_per_side < 0 or self.slippage_pct_per_side < 0 or self.spread_pct < 0:
            raise ValueError("Trading costs cannot be negative")

    @property
    def one_side_pct(self) -> float:
        return self.commission_pct_per_side + self.spread_pct / 2.0 + self.slippage_pct_per_side

    @property
    def round_trip_cost_pct(self) -> float:
        return self.one_side_pct * 2.0

    @classmethod
    def from_legacy(cls, cost_model: object) -> "TradingCostModelV088":
        return cls(
            commission_pct_per_side=float(getattr(cost_model, "commission_pct", 0.0)),
            slippage_pct_per_side=float(getattr(cost_model, "slippage_pct", 0.0)),
            spread_pct=float(getattr(cost_model, "spread_pct", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class EconomicValidationResultV088:
    gross_return_pct: float
    total_cost_pct: float
    net_return_pct: float
    trades: int


class EconomicValidationV088:
    """Apply explicit transaction costs to event-backtest trade returns."""

    @staticmethod
    def validate(
        trade_returns_pct: Iterable[float],
        cost_model: TradingCostModelV088,
    ) -> EconomicValidationResultV088:
        returns = tuple(float(value) for value in trade_returns_pct)
        gross = sum(returns)
        total_cost = len(returns) * cost_model.round_trip_cost_pct
        return EconomicValidationResultV088(
            gross_return_pct=gross,
            total_cost_pct=total_cost,
            net_return_pct=gross - total_cost,
            trades=len(returns),
        )


__all__ = [
    "TradingCostModelV088",
    "EconomicValidationResultV088",
    "EconomicValidationV088",
]
