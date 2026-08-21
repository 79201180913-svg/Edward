from __future__ import annotations

from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient

_SENTINEL = "__edward_compat_fixes_installed__"


def install_compat_fixes(EdwardApp: Any) -> None:
    """Keep compatibility normalization without replacing functional UI pages."""
    if getattr(EdwardApp, _SENTINEL, False):
        return

    original_get_instrument = TInvestAdapterClient.get_instrument

    def normalized_get_instrument(self: TInvestAdapterClient, instrument_id: str) -> dict:
        result = original_get_instrument(self, instrument_id)
        if isinstance(result, dict) and isinstance(result.get("instrument"), dict):
            merged = dict(result["instrument"])
            merged.setdefault("instrument", result["instrument"])
            return merged
        return result

    TInvestAdapterClient.get_instrument = normalized_get_instrument
    setattr(EdwardApp, _SENTINEL, True)
