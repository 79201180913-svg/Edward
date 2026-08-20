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
