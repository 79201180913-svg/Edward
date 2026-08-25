from __future__ import annotations

from typing import Any, Iterable

from edward.api.market_data import MarketDataApi


class MarketService:
    """Application service for current prices, candles and trading availability."""

    def __init__(self, api: MarketDataApi) -> None:
        self._api = api

    def get_last_prices(self, instrument_ids: Iterable[str]) -> Any:
        return self._api.get_last_prices(instrument_ids)

    def get_trading_status(self, instrument_id: str) -> Any:
        return self._api.get_trading_status(instrument_id)

    def get_trading_statuses(self, instrument_ids: Iterable[str]) -> Any:
        return self._api.get_trading_statuses(instrument_ids)

    def get_candles(
        self,
        instrument_id: str,
        *,
        interval: str = "CANDLE_INTERVAL_DAY",
        days: int = 2400,
    ) -> Any:
        return self._api.get_candles(instrument_id, interval=interval, days=days)

    @staticmethod
    def is_api_trade_available(status: Any) -> bool:
        return bool(status.api_trade_available_flag)
