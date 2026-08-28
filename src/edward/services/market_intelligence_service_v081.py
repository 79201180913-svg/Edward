from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Mapping, Sequence

MARKET_INTELLIGENCE_VERSION = "0.8.1"


def _value(data: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(data, Mapping) and name in data:
            return data[name]
        if hasattr(data, name):
            return getattr(data, name)
    return default


def _num(data: Any, *names: str, default: float | None = None) -> float | None:
    value = _value(data, *names, default=default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


@dataclass(frozen=True, slots=True)
class DividendIntelligence:
    yield_pct: float | None
    payout_pct: float | None
    stability_score: float
    growth_score: float
    upcoming_event: bool
    total_return_pct: float | None


@dataclass(frozen=True, slots=True)
class InsiderIntelligence:
    net_buy_value: float
    net_sell_value: float
    net_direction: str
    activity_score: float
    follow_through_pct: float | None


@dataclass(frozen=True, slots=True)
class SessionIntelligence:
    session: str
    quality_score: float
    execution_allowed: bool
    auction_or_clearing: bool


@dataclass(frozen=True, slots=True)
class InstrumentRiskIntelligence:
    dlong_pct: float | None
    dshort_pct: float | None
    dlong_client_pct: float | None
    dshort_client_pct: float | None
    short_enabled: bool
    capital_efficiency_score: float
    risk_score: float


@dataclass(frozen=True, slots=True)
class PortfolioOperationsIntelligence:
    realized_net_pnl: float
    total_fees: float
    total_taxes: float
    total_dividends: float
    total_turnover: float
    net_cash_impact: float


@dataclass(frozen=True, slots=True)
class DerivativesIntelligence:
    kind: str
    available: bool
    open_interest: float | None
    liquidity_score: float
    theoretical_price_gap_pct: float | None
    expiration_risk_score: float


@dataclass(frozen=True, slots=True)
class MarketIntelligenceResult:
    dividends: DividendIntelligence
    insiders: InsiderIntelligence
    session: SessionIntelligence
    instrument_risk: InstrumentRiskIntelligence
    operations: PortfolioOperationsIntelligence
    derivatives: DerivativesIntelligence
    version: str = MARKET_INTELLIGENCE_VERSION


class MarketIntelligenceServiceV081:
    @staticmethod
    def dividends(data: Any = None, upcoming_event: bool = False, price_return_pct: float | None = None) -> DividendIntelligence:
        if data is None:
            return DividendIntelligence(None, None, 0.0, 0.0, upcoming_event, price_return_pct)
        yield_pct = _num(data, "dividend_yield")
        payout = _num(data, "dividend_payout", "payout_ratio")
        growth = _num(data, "dividend_growth")
        regularity = _num(data, "dividend_regularity")
        stability = _clamp(50.0 + (regularity or 0.0) * 0.5)
        growth_score = _clamp(50.0 + (growth or 0.0) * 2.0)
        total_return = (price_return_pct or 0.0) + (yield_pct or 0.0) if price_return_pct is not None or yield_pct is not None else None
        return DividendIntelligence(yield_pct, payout, stability, growth_score, upcoming_event, total_return)

    @staticmethod
    def insiders(transactions: Sequence[Any] | None = None) -> InsiderIntelligence:
        buy = sell = 0.0
        follow = []
        for item in transactions or ():
            action = str(_value(item, "type", "operation", default="")).upper()
            price = _num(item, "price", default=0.0) or 0.0
            quantity = _num(item, "quantity", "amount", default=0.0) or 0.0
            value = abs(price * quantity)
            if "BUY" in action:
                buy += value
            elif "SELL" in action:
                sell += value
            fp = _num(item, "follow_through_pct")
            if fp is not None:
                follow.append(fp)
        net = buy - sell
        direction = "BUY" if net > 0 else "SELL" if net < 0 else "NEUTRAL"
        activity = _clamp(50.0 + min(50.0, abs(net) / max(1.0, buy + sell) * 50.0)) if buy + sell else 0.0
        return InsiderIntelligence(buy, sell, direction, activity, mean(follow) if follow else None)

    @staticmethod
    def session(session: str | None, execution_allowed: bool = True) -> SessionIntelligence:
        value = (session or "UNKNOWN").upper()
        score = {"REGULAR": 100.0, "OPENING_AUCTION": 80.0, "CLOSING_AUCTION": 80.0, "EVENING": 70.0, "PREMARKET": 45.0, "CLEARING": 0.0}.get(value, 50.0)
        blocked = value == "CLEARING"
        return SessionIntelligence(value, score, execution_allowed and not blocked, blocked or "AUCTION" in value)

    @staticmethod
    def instrument_risk(data: Any = None) -> InstrumentRiskIntelligence:
        if data is None:
            return InstrumentRiskIntelligence(None, None, None, None, False, 0.0, 0.0)
        dlong = _num(data, "dlong")
        dshort = _num(data, "dshort")
        dlong_client = _num(data, "dlong_client", "dlongClient")
        dshort_client = _num(data, "dshort_client", "dshortClient")
        short_enabled = bool(_value(data, "short_enabled", "short_enabled_flag", default=False))
        long_rate = dlong_client if dlong_client is not None else dlong
        short_rate = dshort_client if dshort_client is not None else dshort
        risk = _clamp(50.0 + max(0.0, (long_rate or 0.0) - 10.0) * 4.0 + max(0.0, (short_rate or 0.0) - 10.0) * 3.0)
        capital = _clamp(100.0 - max(0.0, (long_rate or 0.0) - 10.0) * 4.0)
        return InstrumentRiskIntelligence(dlong, dshort, dlong_client, dshort_client, short_enabled, capital, risk)

    @staticmethod
    def operations(operations: Sequence[Any] | None = None) -> PortfolioOperationsIntelligence:
        realized = fees = taxes = dividends = turnover = 0.0
        for item in operations or ():
            op = str(_value(item, "type", "operation_type", default="")).upper()
            amount = _num(item, "payment", "amount", "value", "price", default=0.0) or 0.0
            fee = _num(item, "fee", "commission", default=0.0) or 0.0
            tax = _num(item, "tax", default=0.0) or 0.0
            fees += abs(fee)
            taxes += abs(tax)
            turnover += abs(amount) if any(x in op for x in ("BUY", "SELL")) else 0.0
            if "DIVIDEND" in op:
                dividends += amount
            elif "SELL" in op:
                realized += amount - fee - tax
            elif "BUY" in op:
                realized -= amount + fee + tax
            else:
                realized += amount - fee - tax
        return PortfolioOperationsIntelligence(realized, fees, taxes, dividends, turnover, realized + dividends)

    @staticmethod
    def derivatives(data: Any = None) -> DerivativesIntelligence:
        if data is None:
            return DerivativesIntelligence("UNKNOWN", False, None, 0.0, None, 0.0)
        kind = str(_value(data, "kind", "instrument_type", default="DERIVATIVE"))
        oi = _num(data, "open_interest")
        bid = _num(data, "bid_price", "best_bid")
        ask = _num(data, "ask_price", "best_ask")
        theo = _num(data, "theoretical_price", "fair_price")
        mid = (bid + ask) / 2.0 if bid is not None and ask is not None else None
        gap = (mid - theo) / theo * 100.0 if mid is not None and theo not in (None, 0) else None
        liquidity = _clamp(50.0 + min(50.0, (oi or 0.0) / 1000.0))
        days = _num(data, "days_to_expiry")
        expiry_risk = 90.0 if days is not None and days <= 2 else 60.0 if days is not None and days <= 7 else 25.0
        return DerivativesIntelligence(kind, True, oi, liquidity, gap, expiry_risk)

    @classmethod
    def analyze(cls, *, dividend_data: Any = None, dividend_event: bool = False, price_return_pct: float | None = None, insider_transactions: Sequence[Any] | None = None, session_name: str | None = None, session_execution_allowed: bool = True, risk_data: Any = None, operations: Sequence[Any] | None = None, derivatives_data: Any = None) -> MarketIntelligenceResult:
        return MarketIntelligenceResult(
            cls.dividends(dividend_data, dividend_event, price_return_pct),
            cls.insiders(insider_transactions),
            cls.session(session_name, session_execution_allowed),
            cls.instrument_risk(risk_data),
            cls.operations(operations),
            cls.derivatives(derivatives_data),
        )


__all__ = ["MARKET_INTELLIGENCE_VERSION", "DividendIntelligence", "InsiderIntelligence", "SessionIntelligence", "InstrumentRiskIntelligence", "PortfolioOperationsIntelligence", "DerivativesIntelligence", "MarketIntelligenceResult", "MarketIntelligenceServiceV081"]
