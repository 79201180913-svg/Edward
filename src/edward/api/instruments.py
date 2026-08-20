from __future__ import annotations

from typing import Any


class InstrumentsApi:
    """Adapter for T-Invest InstrumentsService operations."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def find_instrument(
        self,
        query: str,
        instrument_kind: Any | None = None,
        api_trade_available_flag: bool | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {"query": query}
        if instrument_kind is not None:
            kwargs["instrument_kind"] = instrument_kind
        if api_trade_available_flag is not None:
            kwargs["api_trade_available_flag"] = api_trade_available_flag
        return self._client.instruments.find_instrument(**kwargs)

    def get_instrument_by(self, id_type: Any, instrument_id: str, class_code: str = "") -> Any:
        return self._client.instruments.get_instrument_by(
            id_type=id_type,
            id=instrument_id,
            class_code=class_code,
        )
