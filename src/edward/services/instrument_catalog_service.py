from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InstrumentCatalogService:
    """Provides a stable instrument-list abstraction over T-Invest catalog APIs."""

    client: Any

    def list(self, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> list[Any]:
        response = self.client.list_instruments(
            instrument_kind=instrument_kind,
            trade_available_only=trade_available_only,
        )
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            value = response.get("instruments", [])
            return list(value) if value is not None else []
        return []

    def search(
        self,
        query: str,
        instrument_kind: str = "SHARE",
        trade_available_only: bool = True,
    ) -> list[Any]:
        """Search the authoritative catalog locally.

        The catalog list is the source of truth for the UI. We deliberately do not
        call FindInstrument here because a transient/not-found response must not make
        the instrument screen fail when the full catalog is available.
        """
        query = query.strip().casefold()
        instruments = self.list(instrument_kind, trade_available_only)
        if not query:
            return instruments

        return [
            instrument
            for instrument in instruments
            if query in str(_field(instrument, "ticker", "")).casefold()
            or query in str(_field(instrument, "name", "")).casefold()
            or query in str(_field(instrument, "uid", "")).casefold()
            or query in str(_field(instrument, "instrument_uid", "")).casefold()
            or query in str(_field(instrument, "figi", "")).casefold()
            or query in str(_field(instrument, "isin", "")).casefold()
        ]


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)
