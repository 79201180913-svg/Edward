from __future__ import annotations

from dataclasses import dataclass


POSITION_SIZING_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class PositionSizingInput:
    action: str
    portfolio_value: float
    current_price: float
    stop_price: float
    risk_per_trade_pct: float
    max_position_weight_pct: float
    available_cash: float
    current_quantity: float = 0.0
    current_weight_pct: float = 0.0
    lot_size: int = 1


@dataclass(frozen=True, slots=True)
class PositionSizingResult:
    recommended_quantity: int
    recommended_value: float
    recommended_weight_pct: float
    risk_amount: float
    risk_pct: float
    capped_by_cash: bool
    capped_by_max_position: bool
    reduction_quantity: int
    version: str = POSITION_SIZING_VERSION


class PositionSizingService:
    """Calculate execution-ready position size within portfolio constraints."""

    @staticmethod
    def _validate(data: PositionSizingInput) -> None:
        if data.portfolio_value <= 0:
            raise ValueError("Стоимость портфеля должна быть положительной")
        if data.current_price <= 0:
            raise ValueError("Текущая цена должна быть положительной")
        if data.risk_per_trade_pct < 0:
            raise ValueError("Риск на сделку не может быть отрицательным")
        if data.max_position_weight_pct < 0:
            raise ValueError("Максимальная доля позиции не может быть отрицательной")
        if data.available_cash < 0:
            raise ValueError("Доступные средства не могут быть отрицательными")
        if data.lot_size <= 0:
            raise ValueError("Размер лота должен быть положительным")

    @classmethod
    def calculate(cls, data: PositionSizingInput) -> PositionSizingResult:
        cls._validate(data)
        action = str(data.action).upper()
        if action not in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}:
            raise ValueError(f"Неподдерживаемое действие: {data.action}")

        if action == "HOLD":
            return PositionSizingResult(0, 0.0, data.current_weight_pct, 0.0, 0.0, False, False, 0)

        stop_distance = abs(data.current_price - data.stop_price)
        risk_amount = data.portfolio_value * data.risk_per_trade_pct / 100.0

        if action in {"REDUCE", "SELL"}:
            target_quantity = 0 if action == "SELL" else int(data.current_quantity // data.lot_size) * data.lot_size // 2
            reduction_quantity = int(max(0, target_quantity))
            value = reduction_quantity * data.current_price
            weight = value / data.portfolio_value * 100.0
            risk_pct = value / data.portfolio_value * 100.0
            return PositionSizingResult(reduction_quantity, value, weight, risk_amount, risk_pct, False, False, reduction_quantity)

        if stop_distance <= 0 or data.risk_per_trade_pct <= 0:
            risk_quantity = 0
        else:
            risk_quantity = int(risk_amount / stop_distance)

        max_value = data.portfolio_value * data.max_position_weight_pct / 100.0
        remaining_capacity = max(0.0, max_value - data.portfolio_value * data.current_weight_pct / 100.0)
        cash_capacity = max(0.0, data.available_cash)

        max_quantity = int(min(remaining_capacity, cash_capacity) / data.current_price)
        recommended_quantity = max(0, min(risk_quantity, max_quantity))
        recommended_quantity = (recommended_quantity // data.lot_size) * data.lot_size

        recommended_value = recommended_quantity * data.current_price
        recommended_weight = recommended_value / data.portfolio_value * 100.0
        realized_risk = recommended_quantity * stop_distance
        realized_risk_pct = realized_risk / data.portfolio_value * 100.0

        return PositionSizingResult(
            recommended_quantity=recommended_quantity,
            recommended_value=round(recommended_value, 8),
            recommended_weight_pct=round(recommended_weight, 8),
            risk_amount=round(realized_risk, 8),
            risk_pct=round(realized_risk_pct, 8),
            capped_by_cash=recommended_quantity < risk_quantity and cash_capacity < remaining_capacity,
            capped_by_max_position=recommended_quantity < risk_quantity and remaining_capacity < cash_capacity,
            reduction_quantity=0,
        )
