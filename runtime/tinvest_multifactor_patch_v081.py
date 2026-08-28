from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import tinvest_adapter as adapter


def _ts(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _structure(value: Any, depth: int = 0) -> Any:
    """Return response shape only; never log financial values."""
    if depth >= 2:
        return type(value).__name__
    if isinstance(value, dict):
        result: dict[str, Any] = {"type": "dict", "keys": tuple(sorted(str(key) for key in value))}
        for key in ("fundamentals", "statistics", "asset_fundamentals", "response", "data", "result", "payload"):
            if key in value:
                nested = value[key]
                if isinstance(nested, list):
                    result[key] = {
                        "type": "list",
                        "count": len(nested),
                        "first": _structure(nested[0], depth + 1) if nested else None,
                    }
                else:
                    result[key] = _structure(nested, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return {
            "type": type(value).__name__,
            "count": len(value),
            "first": _structure(value[0], depth + 1) if value else None,
        }
    return {"type": type(value).__name__}


def _get_asset_fundamentals(self, instrument_id: str):
    assets = [str(instrument_id)]
    adapter.logger.info("[FUNDAMENTALS API REQUEST] assets=%s", tuple(assets))
    result = self._rest_request("InstrumentsService/GetAssetFundamentals", {"assets": assets})
    adapter.logger.info("[FUNDAMENTALS API RAW] response_type=%s structure=%s", type(result).__name__, _structure(result))
    if isinstance(result, dict):
        fundamentals = result.get("fundamentals")
        if isinstance(fundamentals, list):
            adapter.logger.info("[FUNDAMENTALS API COLLECTION] count=%s", len(fundamentals))
            if fundamentals and isinstance(fundamentals[0], dict):
                populated = tuple(sorted(str(key) for key, value in fundamentals[0].items() if value is not None))
                adapter.logger.info("[FUNDAMENTALS API FIRST] keys=%s populated_fields=%s", tuple(sorted(str(key) for key in fundamentals[0])), populated)
    return result


def _get_asset_reports(self, instrument_id: str, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None):
    payload: dict[str, Any] = {"instrumentId": str(instrument_id)}
    if from_dt is not None:
        payload["from"] = _ts(from_dt)
    if to_dt is not None:
        payload["to"] = _ts(to_dt)
    return self._rest_request("InstrumentsService/GetAssetReports", payload)


def _get_dividends(self, instrument_id: str, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None):
    payload: dict[str, Any] = {"instrumentId": str(instrument_id)}
    if from_dt is not None:
        payload["from"] = _ts(from_dt)
    if to_dt is not None:
        payload["to"] = _ts(to_dt)
    return self._rest_request("InstrumentsService/GetDividends", payload)


def _get_risk_rates(self, instrument_ids: list[str]):
    return self._rest_request("InstrumentsService/GetRiskRates", {"instrumentId": [str(value) for value in instrument_ids]})


def _get_insider_deals(self, instrument_id: str, limit: int = 100):
    return self._rest_request("InstrumentsService/GetInsiderDeals", {"instrumentId": str(instrument_id), "limit": max(1, min(int(limit), 100))})


def _get_order_book(self, instrument_id: str, depth: int = 10):
    return self._rest_request("MarketDataService/GetOrderBook", {"instrumentId": str(instrument_id), "depth": max(1, min(int(depth), 50))})


def _get_last_trades(self, instrument_id: str, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None):
    end = to_dt or datetime.now(timezone.utc)
    start = from_dt or end - timedelta(hours=1)
    return self._rest_request("MarketDataService/GetLastTrades", {"instrumentId": str(instrument_id), "from": _ts(start), "to": _ts(end), "tradeSource": "TRADE_SOURCE_ALL"})


def _get_market_values(self, instrument_ids: list[str], values: list[str]):
    return self._rest_request("MarketDataService/GetMarketValues", {"instrumentId": [str(value) for value in instrument_ids], "values": [str(value) for value in values]})


def _get_signals(self, instrument_uid: str | None = None, strategy_id: str | None = None, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None, active: str = "SIGNAL_STATE_ALL"):
    payload: dict[str, Any] = {"active": active}
    if instrument_uid:
        payload["instrumentUid"] = str(instrument_uid)
    if strategy_id:
        payload["strategyId"] = str(strategy_id)
    if from_dt is not None:
        payload["from"] = _ts(from_dt)
    if to_dt is not None:
        payload["to"] = _ts(to_dt)
    return self._rest_request("SignalService/GetSignals", payload)


def _get_signal_strategies(self):
    return self._rest_request("SignalService/GetStrategies", {})


def _get_news(self, limit: int = 1000, cursor: int | None = None):
    payload: dict[str, Any] = {"limit": max(1, min(int(limit), 1000))}
    if cursor is not None:
        payload["cursor"] = int(cursor)
    return self._rest_request("InstrumentsService/News", payload)


def _get_trading_schedules(self, exchange: str | None = None, from_dt: datetime | str | None = None, to_dt: datetime | str | None = None):
    payload: dict[str, Any] = {}
    if exchange:
        payload["exchange"] = str(exchange)
    if from_dt is not None:
        payload["from"] = _ts(from_dt)
    if to_dt is not None:
        payload["to"] = _ts(to_dt)
    return self._rest_request("InstrumentsService/TradingSchedules", payload)


def _get_margin_attributes(self, account_id: str):
    return self._rest_request("UsersService/GetMarginAttributes", {"accountId": str(account_id)})


def _get_account_values(self, account_ids: list[str], values: list[str]):
    return self._rest_request("UsersService/GetAccountValues", {"accounts": [str(value) for value in account_ids], "values": [str(value) for value in values]})


def _get_option(self, instrument_id: str, *, id_type: str = "INSTRUMENT_ID_TYPE_UID", class_code: str | None = None):
    payload: dict[str, Any] = {"idType": id_type, "id": str(instrument_id)}
    if class_code:
        payload["classCode"] = str(class_code)
    return self._rest_request("InstrumentsService/OptionBy", payload)


def _get_future(self, instrument_id: str, *, id_type: str = "INSTRUMENT_ID_TYPE_UID", class_code: str | None = None):
    payload: dict[str, Any] = {"idType": id_type, "id": str(instrument_id)}
    if class_code:
        payload["classCode"] = str(class_code)
    return self._rest_request("InstrumentsService/FutureBy", payload)


def _single_instrument_id(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            if value:
                return str(value[0])
        elif value is not None:
            return str(value)
    raise KeyError(keys[0])


def _instrument_ids(payload: dict[str, Any]) -> list[str]:
    value = payload.get("instrument_id")
    if value is None:
        value = payload.get("instrument_ids")
    if value is None:
        value = payload.get("assets")
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is not None:
        return [str(value)]
    return []


_ROUTES = {
    "/analysis/fundamentals": lambda p: adapter.STATE.get_asset_fundamentals(_single_instrument_id(p, "assets", "instrument_id")),
    "/analysis/reports": lambda p: adapter.STATE.get_asset_reports(p["instrument_id"], p.get("from"), p.get("to")),
    "/analysis/dividends": lambda p: adapter.STATE.get_dividends(p["instrument_id"], p.get("from"), p.get("to")),
    "/analysis/risk-rates": lambda p: adapter.STATE.get_risk_rates(_instrument_ids(p)),
    "/analysis/insider-deals": lambda p: adapter.STATE.get_insider_deals(p["instrument_id"], p.get("limit", 100)),
    "/analysis/order-book": lambda p: adapter.STATE.get_order_book(p["instrument_id"], p.get("depth", 10)),
    "/analysis/last-trades": lambda p: adapter.STATE.get_last_trades(p["instrument_id"], p.get("from"), p.get("to")),
    "/analysis/market-values": lambda p: adapter.STATE.get_market_values(_instrument_ids(p), p.get("values", [])),
    "/analysis/signals": lambda p: adapter.STATE.get_signals(p.get("instrument_uid"), p.get("strategy_id"), p.get("from"), p.get("to"), p.get("active", "SIGNAL_STATE_ALL")),
    "/analysis/signal-strategies": lambda p: adapter.STATE.get_signal_strategies(),
    "/analysis/news": lambda p: adapter.STATE.get_news(p.get("limit", 1000), p.get("cursor")),
    "/analysis/trading-schedules": lambda p: adapter.STATE.get_trading_schedules(p.get("exchange"), p.get("from"), p.get("to")),
    "/analysis/margin-attributes": lambda p: adapter.STATE.get_margin_attributes(p["account_id"]),
    "/analysis/account-values": lambda p: adapter.STATE.get_account_values(p.get("account_ids", []), p.get("values", [])),
    "/analysis/option": lambda p: adapter.STATE.get_option(p["instrument_id"], id_type=p.get("id_type", "INSTRUMENT_ID_TYPE_UID"), class_code=p.get("class_code")),
    "/analysis/future": lambda p: adapter.STATE.get_future(p["instrument_id"], id_type=p.get("id_type", "INSTRUMENT_ID_TYPE_UID"), class_code=p.get("class_code")),
}


def install() -> None:
    if getattr(adapter, "_multifactor_v081_installed", False):
        return

    methods = {
        "get_asset_fundamentals": _get_asset_fundamentals,
        "get_asset_reports": _get_asset_reports,
        "get_dividends": _get_dividends,
        "get_risk_rates": _get_risk_rates,
        "get_insider_deals": _get_insider_deals,
        "get_order_book": _get_order_book,
        "get_last_trades": _get_last_trades,
        "get_market_values": _get_market_values,
        "get_signals": _get_signals,
        "get_signal_strategies": _get_signal_strategies,
        "get_news": _get_news,
        "get_trading_schedules": _get_trading_schedules,
        "get_margin_attributes": _get_margin_attributes,
        "get_account_values": _get_account_values,
        "get_option": _get_option,
        "get_future": _get_future,
    }
    for name, method in methods.items():
        setattr(adapter.AdapterState, name, method)

    original_do_post = adapter.Handler.do_POST

    def do_post(self):
        if self.path not in _ROUTES:
            return original_do_post(self)
        try:
            payload = self._read_json()
            result = _ROUTES[self.path](payload)
            self._send(200, result)
        except Exception as exc:
            adapter.logger.exception("[MULTIFACTOR V0.8.1] %s", exc)
            self._send(500, {"error": str(exc), "type": type(exc).__name__})

    adapter.Handler.do_POST = do_post
    adapter._multifactor_v081_installed = True


__all__ = ["install"]
