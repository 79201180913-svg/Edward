from __future__ import annotations

from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient


_INSTALLED = False


def install_sandbox_data_routing() -> None:
    """Keep the adapter client's normalized sandbox responses intact."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_get_positions = TInvestAdapterClient.get_positions
    original_get_portfolio = TInvestAdapterClient.get_portfolio

    def _get_positions(self: TInvestAdapterClient, account_id: str) -> dict[str, Any]:
        # The client already routes SANDBOX to SandboxService and normalizes
        # GetSandboxPositions. Do not bypass that layer with a raw HTTP call.
        return original_get_positions(self, account_id)

    def _get_portfolio(self: TInvestAdapterClient, account_id: str) -> dict[str, Any]:
        # The client already routes SANDBOX to SandboxService and returns the
        # normalized PortfolioResponse. Do not bypass that layer.
        return original_get_portfolio(self, account_id)

    TInvestAdapterClient.get_positions = _get_positions
    TInvestAdapterClient.get_portfolio = _get_portfolio
    _INSTALLED = True
