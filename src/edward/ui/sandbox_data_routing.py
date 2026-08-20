from __future__ import annotations

from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient


_INSTALLED = False


def install_sandbox_data_routing() -> None:
    """Route generic positions/portfolio calls to SandboxService in SANDBOX only."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_get_positions = TInvestAdapterClient.get_positions
    original_get_portfolio = TInvestAdapterClient.get_portfolio

    def _get_positions(self: TInvestAdapterClient, account_id: str) -> dict[str, Any]:
        try:
            health = self.health()
            if str(health.get("environment", "")).lower() == "sandbox":
                return self._request("POST", "/accounts/sandbox-positions", {"account_id": account_id})
        except Exception:
            pass
        return original_get_positions(self, account_id)

    def _get_portfolio(self: TInvestAdapterClient, account_id: str) -> dict[str, Any]:
        try:
            health = self.health()
            if str(health.get("environment", "")).lower() == "sandbox":
                return self._request("POST", "/accounts/sandbox-portfolio", {"account_id": account_id})
        except Exception:
            pass
        return original_get_portfolio(self, account_id)

    TInvestAdapterClient.get_positions = _get_positions
    TInvestAdapterClient.get_portfolio = _get_portfolio
    _INSTALLED = True
