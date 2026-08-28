from __future__ import annotations

from datetime import datetime
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient


def _post(client: TInvestAdapterClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return client._request("POST", path, payload)


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    normalized = value if value.tzinfo else value.astimezone()
    return normalized.isoformat()


def get_asset_fundamentals(self: TInvestAdapterClient, instrument_id: str) -> dict[str, Any]:
    return _post(self, "/analysis/fundamentals", {"instrument_id": instrument_id})


def get_asset_reports(self: TInvestAdapterClient, instrument_id: str, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None) -> dict[str, Any]:
    return _post(self, "/analysis/reports", {"instrument_id": instrument_id, "from": _iso(from_dt), "to": _iso(to_dt)})


def get_dividends(self: TInvestAdapterClient, instrument_id: str, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None) -> dict[str, Any]:
    return _post(self, "/analysis/dividends", {"instrument_id": instrument_id, "from": _iso(from_dt), "to": _iso(to_dt)})


def get_risk_rates(self: TInvestAdapterClient, instrument_ids: list[str]) -> dict[str, Any]:
    return _post(self, "/analysis/risk-rates", {"instrument_ids": instrument_ids})


def get_insider_deals(self: TInvestAdapterClient, instrument_id: str, limit: int = 100) -> dict[str, Any]:
    return _post(self, "/analysis/insider-deals", {"instrument_id": instrument_id, "limit": max(1, min(int(limit), 100))})


def get_order_book(self: TInvestAdapterClient, instrument_id: str, depth: int = 10) -> dict[str, Any]:
    return _post(self, "/analysis/order-book", {"instrument_id": instrument_id, "depth": max(1, min(int(depth), 50))})


def get_last_trades(self: TInvestAdapterClient, instrument_id: str, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None) -> dict[str, Any]:
    return _post(self, "/analysis/last-trades", {"instrument_id": instrument_id, "from": _iso(from_dt), "to": _iso(to_dt)})


def get_market_values(self: TInvestAdapterClient, instrument_ids: list[str], values: list[str]) -> dict[str, Any]:
    return _post(self, "/analysis/market-values", {"instrument_ids": instrument_ids, "values": values})


def get_signals(self: TInvestAdapterClient, instrument_uid: str | None = None, strategy_id: str | None = None, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None, active: str = "SIGNAL_STATE_ALL") -> dict[str, Any]:
    return _post(self, "/analysis/signals", {"instrument_uid": instrument_uid, "strategy_id": strategy_id, "from": _iso(from_dt), "to": _iso(to_dt), "active": active})


def get_signal_strategies(self: TInvestAdapterClient) -> dict[str, Any]:
    return _post(self, "/analysis/signal-strategies", {})


def get_news(self: TInvestAdapterClient, limit: int = 1000, cursor: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"limit": max(1, min(int(limit), 1000))}
    if cursor is not None:
        payload["cursor"] = int(cursor)
    return _post(self, "/analysis/news", payload)


def get_trading_schedules(self: TInvestAdapterClient, exchange: str | None = None, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None) -> dict[str, Any]:
    return _post(self, "/analysis/trading-schedules", {"exchange": exchange, "from": _iso(from_dt), "to": _iso(to_dt)})


def get_margin_attributes(self: TInvestAdapterClient, account_id: str) -> dict[str, Any]:
    return _post(self, "/analysis/margin-attributes", {"account_id": account_id})


def get_account_values(self: TInvestAdapterClient, account_ids: list[str], values: list[str]) -> dict[str, Any]:
    return _post(self, "/analysis/account-values", {"account_ids": account_ids, "values": values})


def get_option(self: TInvestAdapterClient, instrument_id: str, id_type: str = "INSTRUMENT_ID_TYPE_UID", class_code: str | None = None) -> dict[str, Any]:
    return _post(self, "/analysis/option", {"instrument_id": instrument_id, "id_type": id_type, "class_code": class_code})


def get_future(self: TInvestAdapterClient, instrument_id: str, id_type: str = "INSTRUMENT_ID_TYPE_UID", class_code: str | None = None) -> dict[str, Any]:
    return _post(self, "/analysis/future", {"instrument_id": instrument_id, "id_type": id_type, "class_code": class_code})


def install() -> None:
    methods = {
        "get_asset_fundamentals": get_asset_fundamentals,
        "get_asset_reports": get_asset_reports,
        "get_dividends": get_dividends,
        "get_risk_rates": get_risk_rates,
        "get_insider_deals": get_insider_deals,
        "get_order_book": get_order_book,
        "get_last_trades": get_last_trades,
        "get_market_values": get_market_values,
        "get_signals": get_signals,
        "get_signal_strategies": get_signal_strategies,
        "get_news": get_news,
        "get_trading_schedules": get_trading_schedules,
        "get_margin_attributes": get_margin_attributes,
        "get_account_values": get_account_values,
        "get_option": get_option,
        "get_future": get_future,
    }
    for name, method in methods.items():
        setattr(TInvestAdapterClient, name, method)


__all__ = ["install"]
