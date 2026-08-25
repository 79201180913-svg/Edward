from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edward.services.decision_engine import PortfolioContextData, PositionContextData


@dataclass(frozen=True, slots=True)
class PortfolioDecisionContext:
    portfolio: PortfolioContextData
    position: PositionContextData


class PortfolioDecisionContextService:
    """Build Decision Engine portfolio/position context from T-Invest payloads."""

    def build(self, *, positions: Any, portfolio: Any | None, instrument_uid: str) -> PortfolioDecisionContext:
        money = _items(positions, "money")
        securities = _items(positions, "securities")
        portfolio_rows = _items(portfolio, "positions")

        portfolio_value = _decimal(_field(portfolio, "total_amount_portfolio", None))
        if portfolio_value == Decimal("0"):
            portfolio_value = _decimal(_field(portfolio, "total_amount_currencies", None))

        available_cash = Decimal("0")
        blocked_cash = Decimal("0")
        for item in money:
            available_cash += _decimal(_first(item, "available", "available_value"))
            blocked_cash += _decimal(_first(item, "blocked", "blocked_value"))

        row = next(
            (
                item
                for item in securities + portfolio_rows
                if str(_field(item, "instrument_uid", _field(item, "uid", ""))) == instrument_uid
            ),
            None,
        )

        position = _position(row)
        current_value = _decimal(_first(row, "current_value", "value")) if row is not None else Decimal("0")
        if current_value == Decimal("0") and row is not None:
            current_value = position.quantity * position.current_price if position.current_price is not None else Decimal("0")

        current_weight = 0.0
        if portfolio_value:
            current_weight = float(current_value / portfolio_value * Decimal("100"))

        position = PositionContextData(
            quantity=position.quantity,
            average_price=position.average_price,
            current_price=position.current_price,
            pnl=position.pnl,
            portfolio_weight_pct=current_weight,
            target_weight_pct=position.target_weight_pct,
        )

        available = portfolio is not None or positions is not None
        portfolio_context = PortfolioContextData(
            portfolio_value=float(portfolio_value) if portfolio_value else None,
            available_cash=float(available_cash),
            blocked_cash=float(blocked_cash),
            current_weight_pct=current_weight,
            target_weight_pct=position.target_weight_pct,
            max_position_weight_pct=None,
            allows_buy=True,
            allows_add=True,
            available=available,
        )
        return PortfolioDecisionContext(portfolio=portfolio_context, position=position)


def _position(item: Any) -> PositionContextData:
    if item is None:
        return PositionContextData()
    quantity = _decimal(_first(item, "quantity", "balance"))
    average_price = _decimal(_first(item, "average_position_price", "average_price"))
    current_price = _decimal(_first(item, "current_price", "price"))
    pnl = _decimal(_first(item, "expected_yield", "expected_yield_fifo"))
    return PositionContextData(
        quantity=float(quantity),
        average_price=float(average_price) if average_price else None,
        current_price=float(current_price) if current_price else None,
        pnl=float(pnl) if pnl else None,
    )


def _items(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    raw = _field(value, name, [])
    return list(raw or [])


def _first(value: Any, *names: str) -> Any:
    for name in names:
        current = _field(value, name, None)
        if current is not None:
            return current
    return None


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        units = getattr(value, "units", None)
        nano = getattr(value, "nano", None)
        if units is not None or nano is not None:
            return Decimal(str(units or 0)) + Decimal(str(nano or 0)) / Decimal("1000000000")
    except Exception:
        pass
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")
