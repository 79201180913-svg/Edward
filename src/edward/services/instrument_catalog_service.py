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
        """Search the catalog locally after loading the authoritative instrument list.

        T-Invest FindInstrument is treated as an optimization, not as the only source
        of truth. This prevents a transient/not-found response from breaking the UI.
        """
        query = query.strip().casefold()
        if not query:
            return self.list(instrument_kind, trade_available_only)

        result = self.client.find_instrument(query, trade_available_only)
        if isinstance(result, dict):
            instruments = result.get("instruments")
            if instruments:
                return list(instruments)

        return [
            instrument
            for instrument in self.list(instrument_kind, trade_available_only)
            if query in str(_field(instrument, "ticker", "")).casefold()
            or query in str(_field(instrument, "name", "")).casefold()
            or query in str(_field(instrument, "uid", "")).casefold()
            or query in str(_field(instrument, "figi", "")).casefold()
        ]


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)
