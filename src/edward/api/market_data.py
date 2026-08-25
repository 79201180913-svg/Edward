from __future__ import annotations

from typing import Any, Iterable


class MarketDataApi:
    """Adapter for T-Invest MarketDataService operations."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_last_prices(self, instrument_ids: Iterable[str]) -> Any:
        return self._client.market_data.get_last_prices(
            instrument_id=list(instrument_ids)
        )

    def get_trading_status(self, instrument_id: str) -> Any:
        return self._client.market_data.get_trading_status(
            instrument_id=instrument_id
        )

    def get_trading_statuses(self, instrument_ids: Iterable[str]) -> Any:
        return self._client.market_data.get_trading_statuses(
            instrument_id=list(instrument_ids)
        )

    def get_candles(
        self,
        instrument_id: str,
        *,
        interval: str = "CANDLE_INTERVAL_DAY",
        days: int = 2400,
    ) -> Any:
        return self._client.get_candles(
            instrument_uid=instrument_id,
            interval=interval,
            days=days,
        )
