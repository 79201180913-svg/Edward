from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InstrumentCatalogService:
    """Application service for the authoritative T-Invest instrument catalog."""

    client: Any

    def list(self, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> list[Any]:
        response = self.client.list_instruments(instrument_kind=instrument_kind, trade_available_only=trade_available_only)
        instruments = self._as_list(response, "instruments")
        return self._enrich(instruments, instrument_kind)

    def search(self, query: str, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> list[Any]:
        """Filter the already loaded authoritative catalog locally."""
        query = query.strip().casefold()
        instruments = self.list(instrument_kind, trade_available_only)
        if not query:
            return instruments
        return [
            instrument for instrument in instruments
            if any(query in str(_field(instrument, name, "")).casefold() for name in ("ticker", "name", "uid", "instrument_uid", "figi", "isin"))
        ]

    def trading_status(self, instrument_uid: str) -> Any:
        return self.client.get_trading_status(instrument_uid)

    def _enrich(self, instruments: list[Any], instrument_kind: str) -> list[Any]:
        """Add bulk prices and stable metadata without per-row trading-status calls."""
        ids = [_uid(item) for item in instruments if _uid(item)]
        prices: dict[str, Any] = {}
        if ids:
            try:
                prices = _index_response(self.client.get_last_prices(ids), "last_prices")
            except Exception:
                prices = {}

        result: list[Any] = []
        for instrument in instruments:
            item = dict(instrument) if isinstance(instrument, dict) else instrument
            uid = _uid(instrument)
            price = prices.get(uid)
            if isinstance(item, dict):
                item["instrument_kind"] = instrument_kind
                item["last_price"] = _field(price, "price", _field(price, "last_price", ""))
                item["buy_available"] = _field(instrument, "buy_available_flag", False)
                item["sell_available"] = _field(instrument, "sell_available_flag", False)
                item["api_trade_available"] = _field(instrument, "api_trade_available_flag", False)
                item["min_price_increment"] = _field(instrument, "min_price_increment", _field(instrument, "min_price_increment_value", ""))
            result.append(item)
        return result

    @staticmethod
    def _as_list(response: Any, name: str) -> list[Any]:
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            value = response.get(name, [])
            return list(value) if value is not None else []
        return []


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _uid(value: Any) -> str:
    return str(_field(value, "uid", _field(value, "instrument_uid", "")))


def _index_response(response: Any, collection_name: str) -> dict[str, Any]:
    items = response if isinstance(response, list) else _field(response, collection_name, [])
    if items is None:
        return {}
    indexed: dict[str, Any] = {}
    for item in items:
        uid = _uid(item)
        if uid:
            indexed[uid] = item
    return indexed
