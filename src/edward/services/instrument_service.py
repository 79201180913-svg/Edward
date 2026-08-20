from __future__ import annotations

from typing import Any

from edward.api.instruments import InstrumentsApi


class InstrumentService:
    """Application service for instrument discovery and details."""

    def __init__(self, api: InstrumentsApi) -> None:
        self._api = api

    def find(self, query: str, api_trade_available_only: bool = True) -> Any:
        return self._api.find_instrument(
            query=query,
            api_trade_available_flag=api_trade_available_only,
        )

    def get_by(self, id_type: Any, instrument_id: str, class_code: str = "") -> Any:
        return self._api.get_instrument_by(id_type, instrument_id, class_code)
