from __future__ import annotations

from dataclasses import fields
from typing import Any

from edward.domain import TradingPathContextV015
from edward.services.decision_engine import PortfolioContextData, PositionContextData


class TradingPathContextFactoryV015:
    """Create the canonical context envelope without owning any business decision."""

    @staticmethod
    def build(
        *,
        instrument: Any | None = None,
        portfolio: PortfolioContextData | None = None,
        position: PositionContextData | None = None,
    ) -> TradingPathContextV015 | None:
        if instrument is None and portfolio is None and position is None:
            return None

        names = {field.name for field in fields(TradingPathContextV015)}
        values = {
            name: _field(instrument, name, None)
            for name in names
            if name not in {"instrument_metadata", "current_price", "current_weight_pct"}
        }
        values["instrument_metadata"] = instrument

        if portfolio is not None:
            values["current_weight_pct"] = float(portfolio.current_weight_pct or 0.0)
            values["max_position_weight_pct"] = portfolio.max_position_weight_pct

        if position is not None:
            if values.get("current_price") is None:
                values["current_price"] = position.current_price
            if not values.get("current_weight_pct"):
                values["current_weight_pct"] = float(position.portfolio_weight_pct or 0.0)

        if values.get("current_price") is None:
            values["current_price"] = _field(instrument, "last_price", None)

        return TradingPathContextV015(**values)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


__all__ = ["TradingPathContextFactoryV015"]
