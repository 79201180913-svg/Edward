from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class TInvestAdapterClient:
    """HTTP client for the local Python 3.12 T-Invest adapter."""

    base_url: str = "http://127.0.0.1:8765"
    timeout: float = 20.0

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except Exception:
                body = {"error": "http_error", "message": str(exc)}
            raise RuntimeError(body.get("message", body.get("error", str(exc)))) from exc
        except URLError as exc:
            raise RuntimeError(f"T-Invest adapter is unavailable: {exc.reason}") from exc

    def health(self) -> dict:
        return self._request("GET", "/health")

    def get_accounts(self) -> dict:
        return self._request("POST", "/accounts", {})

    def create_sandbox_account(self, name: str | None = None) -> dict:
        return self._request("POST", "/accounts/create", {"name": name} if name else {})

    def close_sandbox_account(self, account_id: str) -> dict:
        return self._request("POST", "/accounts/close", {"account_id": account_id})

    def get_portfolio(self, account_id: str) -> dict:
        return self._request("POST", "/portfolio", {"account_id": account_id})

    def get_positions(self, account_id: str) -> dict:
        return self._request("POST", "/positions", {"account_id": account_id})

    def find_instrument(self, query: str, trade_available_only: bool = True) -> dict:
        return self._request(
            "POST",
            "/instruments/search",
            {"query": query, "api_trade_available_flag": trade_available_only},
        )

    def get_instrument(self, instrument_uid: str) -> dict:
        return self._request("POST", "/instruments/get", {"instrument_uid": instrument_uid})

    def get_last_prices(self, instrument_ids: list[str]) -> dict:
        return self._request("POST", "/market/last-prices", {"instrument_ids": instrument_ids})

    def get_trading_status(self, instrument_id: str) -> dict:
        return self._request("POST", "/market/trading-status", {"instrument_id": instrument_id})

    def get_orders(self, account_id: str) -> dict:
        return self._request("POST", "/orders", {"account_id": account_id})

    def get_order_state(self, account_id: str, order_id: str) -> dict:
        return self._request("POST", "/orders/state", {"account_id": account_id, "order_id": order_id})

    def post_order(self, request: dict) -> dict:
        return self._request("POST", "/orders/create", request)

    def cancel_order(self, account_id: str, order_id: str) -> dict:
        return self._request("POST", "/orders/cancel", {"account_id": account_id, "order_id": order_id})

    def replace_order(self, request: dict) -> dict:
        return self._request("POST", "/orders/replace", request)
