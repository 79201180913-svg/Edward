from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


def _get(data: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(data, Mapping) and name in data:
            return data[name]
        if hasattr(data, name):
            return getattr(data, name)
    return default


def quotation_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping):
        if "units" in value or "nano" in value:
            try:
                return float(value.get("units", 0)) + float(value.get("nano", 0)) / 1_000_000_000.0
            except (TypeError, ValueError):
                return None
        if "value" in value:
            return quotation_to_float(value["value"])
        for key in ("price", "yield_value", "amount"):
            if key in value:
                return quotation_to_float(value[key])
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def map_fundamentals(statistics: Any) -> dict[str, float | None]:
    revenue = quotation_to_float(_get(statistics, "revenue_ttm"))
    fcf = quotation_to_float(_get(statistics, "free_cash_flow_ttm"))
    return {
        "roe": quotation_to_float(_get(statistics, "roe")),
        "roic": quotation_to_float(_get(statistics, "roic")),
        "net_margin": quotation_to_float(_get(statistics, "net_margin_mrq")),
        "revenue_growth": quotation_to_float(_get(statistics, "one_year_annual_revenue_growth_rate", "revenue_change_five_years")),
        "eps_growth": quotation_to_float(_get(statistics, "eps_change_five_years")),
        "ebitda_growth": quotation_to_float(_get(statistics, "ebitda_change_five_years")),
        "net_debt_to_ebitda": quotation_to_float(_get(statistics, "net_debt_to_ebitda")),
        "current_ratio": quotation_to_float(_get(statistics, "current_ratio_mrq")),
        # Normalize cash flow to a margin-like percentage before it reaches the generic scorer.
        "free_cash_flow": (fcf / revenue * 100.0) if fcf is not None and revenue not in (None, 0) else None,
        "pe": quotation_to_float(_get(statistics, "pe_ratio_ttm")),
        "ps": quotation_to_float(_get(statistics, "price_to_sales_ttm")),
        "pb": quotation_to_float(_get(statistics, "price_to_book_ttm")),
        "p_fcf": quotation_to_float(_get(statistics, "price_to_free_cash_flow_ttm")),
        "dividend_yield": quotation_to_float(_get(statistics, "dividend_yield_daily_ttm", "forward_annual_dividend_yield")),
        "dividend_payout": quotation_to_float(_get(statistics, "dividend_payout_ratio_fy")),
        "dividend_growth": quotation_to_float(_get(statistics, "five_year_annual_dividend_growth_rate")),
        "dividend_regularity": 100.0 if _get(statistics, "regularity", default=None) else None,
    }


def map_risk_rates(risk_response: Any) -> dict[str, Any]:
    items = _get(risk_response, "risk_rates", "items", default=None)
    if items is None:
        items = risk_response if isinstance(risk_response, list) else []
    if not items:
        return {}
    first = items[0]
    long_rate = quotation_to_float(_get(first, "long_risk_rate", "dlong", "dlong_client"))
    short_rate = quotation_to_float(_get(first, "short_risk_rate", "dshort", "dshort_client"))
    return {
        "dlong": long_rate,
        "dshort": short_rate,
        "dlong_client": long_rate,
        "dshort_client": short_rate,
        "short_enabled": bool(_get(first, "short_enabled_flag", default=False)),
    }


def map_order_book(response: Any) -> dict[str, Any]:
    bids = _get(response, "bids", default=[]) or []
    asks = _get(response, "asks", default=[]) or []
    return {
        "bids": [{"price": quotation_to_float(_get(item, "price")), "quantity": quotation_to_float(_get(item, "quantity", "volume")) or 0.0} for item in bids],
        "asks": [{"price": quotation_to_float(_get(item, "price")), "quantity": quotation_to_float(_get(item, "quantity", "volume")) or 0.0} for item in asks],
    }


def map_trades(response: Any) -> list[dict[str, Any]]:
    items = _get(response, "trades", "items", default=[]) or []
    return [
        {"direction": str(_get(item, "direction", default="")), "quantity": quotation_to_float(_get(item, "quantity", "volume")) or 0.0}
        for item in items
    ]


def map_signal(item: Any) -> dict[str, Any]:
    return {
        "signal_id": str(_get(item, "signal_id", default="")),
        "strategy_id": str(_get(item, "strategy_id", default="")),
        "strategy_name": _get(item, "strategy_name"),
        "instrument_uid": _get(item, "instrument_uid"),
        "create_dt": _get(item, "create_dt"),
        "direction": _get(item, "direction", default=""),
        "initial_price": quotation_to_float(_get(item, "initial_price")),
        "target_price": quotation_to_float(_get(item, "target_price")),
        "probability": quotation_to_float(_get(item, "probability")),
        "stoploss": quotation_to_float(_get(item, "stoploss")),
        "close_price": quotation_to_float(_get(item, "close_price")),
        "close_dt": _get(item, "close_dt"),
    }


def map_dividend(event: Any) -> dict[str, Any]:
    return {
        "dividend_yield": quotation_to_float(_get(event, "yield_value", "dividend_yield")),
        "dividend_payout": quotation_to_float(_get(event, "dividend_payout", "payout_ratio")),
        "dividend_growth": quotation_to_float(_get(event, "dividend_growth")),
        "dividend_regularity": quotation_to_float(_get(event, "regularity")),
        "declared_date": _get(event, "declared_date"),
        "last_buy_date": _get(event, "last_buy_date"),
        "record_date": _get(event, "record_date"),
        "payment_date": _get(event, "payment_date"),
    }


def map_insider(item: Any) -> dict[str, Any]:
    return {
        "type": _get(item, "direction", "type", default=""),
        "price": quotation_to_float(_get(item, "price")),
        "quantity": quotation_to_float(_get(item, "quantity")) or 0.0,
        "percentage": quotation_to_float(_get(item, "percentage")),
        "investor_position": _get(item, "investor_position"),
        "disclosure_date": _get(item, "disclosure_date"),
    }


def map_news(item: Any) -> dict[str, Any]:
    return {
        "id": _get(item, "id"),
        "source": _get(item, "source"),
        "title": _get(item, "title", default=""),
        "summary": _get(item, "summary"),
        "content": _get(item, "content"),
        "priority": bool(_get(item, "priority", default=False)),
        "ts": _get(item, "ts"),
        "instrument_id": _get(item, "instrument_id", default=[]),
    }


__all__ = [
    "quotation_to_float", "map_fundamentals", "map_risk_rates", "map_order_book",
    "map_trades", "map_signal", "map_dividend", "map_insider", "map_news",
]
