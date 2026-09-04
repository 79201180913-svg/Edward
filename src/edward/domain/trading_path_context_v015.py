from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradingPathContextV015:
    """Immutable context envelope preserved alongside canonical path analysis."""

    fundamentals: object | None = None
    instrument_metadata: object | None = None
    news: object | None = None
    news_overlay: object | None = None
    signals: object | None = None
    events: object | None = None
    dividends: object | None = None
    insider: object | None = None
    risk_metadata: object | None = None
    session: object | None = None
    order_book: object | None = None
    trades: object | None = None
    current_signal: object | None = None
    historical_signals: object | None = None
    historical_gaps_pct: object | None = None
    historical_event_vol_pct: object | None = None
    session_name: str | None = None
    session_execution_allowed: bool = True
    current_price: float | None = None
    current_weight_pct: float = 0.0
    marginal_risk_pct: float = 0.0
    diversification_benefit_pct: float = 0.0
    expected_return_impact_pct: float = 0.0
    max_position_weight_pct: float | None = None


__all__ = ["TradingPathContextV015"]
