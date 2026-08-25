from __future__ import annotations

from dataclasses import dataclass


TRADING_COSTS_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class TradingCostsInput:
    action: str
    gross_return_pct: float
    trade_value: float
    commission_pct: float = 0.0
    spread_pct: float = 0.0
    slippage_pct: float = 0.0
    liquidity_impact_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class TradingCostsResult:
    gross_return_pct: float
    commission_pct: float
    spread_pct: float
    slippage_pct: float
    liquidity_impact_pct: float
    total_cost_pct: float
    total_cost_value: float
    net_return_pct: float
    profitable_after_costs: bool
    version: str = TRADING_COSTS_VERSION


class TradingCostsService:
    """Convert gross expected trade return into net expected return."""

    @staticmethod
    def _validate(data: TradingCostsInput) -> None:
        if data.trade_value < 0:
            raise ValueError("Стоимость сделки не может быть отрицательной")
        for name, value in (
            ("commission_pct", data.commission_pct),
            ("spread_pct", data.spread_pct),
            ("slippage_pct", data.slippage_pct),
            ("liquidity_impact_pct", data.liquidity_impact_pct),
        ):
            if value < 0:
                raise ValueError(f"{name} не может быть отрицательной")

    @classmethod
    def calculate(cls, data: TradingCostsInput) -> TradingCostsResult:
        cls._validate(data)
        action = str(data.action).upper()
        if action not in {"BUY", "ADD", "SELL", "REDUCE", "HOLD"}:
            raise ValueError(f"Неподдерживаемое действие: {data.action}")

        gross = float(data.gross_return_pct)
        total_cost_pct = (
            float(data.commission_pct)
            + float(data.spread_pct)
            + float(data.slippage_pct)
            + float(data.liquidity_impact_pct)
        )
        total_cost_value = float(data.trade_value) * total_cost_pct / 100.0
        net = gross - total_cost_pct if action != "HOLD" else gross

        return TradingCostsResult(
            gross_return_pct=round(gross, 8),
            commission_pct=round(data.commission_pct, 8),
            spread_pct=round(data.spread_pct, 8),
            slippage_pct=round(data.slippage_pct, 8),
            liquidity_impact_pct=round(data.liquidity_impact_pct, 8),
            total_cost_pct=round(total_cost_pct, 8),
            total_cost_value=round(total_cost_value, 8),
            net_return_pct=round(net, 8),
            profitable_after_costs=net > 0,
        )
