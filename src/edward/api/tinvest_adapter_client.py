from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class TInvestAdapterClient:
    base_url: str = "http://127.0.0.1:8765"
    timeout: float = 20.0

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(f"{self.base_url}{path}", data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except Exception:
                body = {"error": "http_error", "message": str(exc)}
            error = RuntimeError(body.get("message", body.get("error", str(exc))))
            setattr(error, "status_code", exc.code)
            setattr(error, "error_code", body.get("code", body.get("error")))
            setattr(error, "retryable", exc.code in (408, 409, 429, 500, 502, 503, 504))
            raise error from exc
        except URLError as exc:
            error = RuntimeError(f"T-Invest adapter is unavailable: {exc.reason}")
            setattr(error, "retryable", True)
            raise error from exc

    def health(self) -> dict: return self._request("GET", "/health")
    def get_accounts(self) -> dict: return self._request("POST", "/accounts", {})
    def create_sandbox_account(self, name: str | None = None) -> dict: return self._request("POST", "/accounts/create", {"name": name} if name else {})
    def close_sandbox_account(self, account_id: str) -> dict: return self._request("POST", "/accounts/close", {"account_id": account_id})
    def sandbox_pay_in(self, account_id: str, amount: Any) -> dict: return self._request("POST", "/accounts/pay-in", {"account_id": account_id, "amount": str(amount)})
    def get_sandbox_positions(self, account_id: str) -> dict: return self._request("POST", "/accounts/sandbox-positions", {"account_id": account_id})
    def get_sandbox_portfolio(self, account_id: str) -> dict: return self._request("POST", "/accounts/sandbox-portfolio", {"account_id": account_id})
    def get_sandbox_withdraw_limits(self, account_id: str) -> dict: return self._request("POST", "/accounts/sandbox-withdraw-limits", {"account_id": account_id})

    @staticmethod
    def _money_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, dict):
            if "units" in value or "nano" in value:
                return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
            for key in ("available_value", "available", "blocked_value", "blocked", "value"):
                if key in value:
                    return TInvestAdapterClient._money_decimal(value[key])
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    @classmethod
    def _normalize_sandbox_positions(cls, positions: dict) -> dict:
        result = dict(positions or {})
        normalized_money: list[dict] = []
        for item in result.get("money", []) or []:
            if not isinstance(item, dict):
                continue
            currency = str(item.get("currency", "")).upper()
            if not currency:
                continue
            available = cls._money_decimal(item.get("available_value", item.get("available", item)))
            blocked = cls._money_decimal(item.get("blocked_value", item.get("blocked", 0)))
            normalized_money.append({"currency": currency, "available": cls._quotation_payload(available), "blocked": cls._quotation_payload(blocked)})
        result["money"] = normalized_money
        return result

    def get_portfolio(self, account_id: str) -> dict:
        if str(self.health().get("environment", "")).lower() == "sandbox":
            return self.get_sandbox_portfolio(account_id)
        return self._request("POST", "/portfolio", {"account_id": account_id})

    def get_positions(self, account_id: str) -> dict:
        if str(self.health().get("environment", "")).lower() != "sandbox":
            return self._request("POST", "/positions", {"account_id": account_id})
        return self._normalize_sandbox_positions(self.get_sandbox_positions(account_id))

    def find_instrument(self, query: str, trade_available_only: bool = True, instrument_kind: str = "INSTRUMENT_TYPE_UNSPECIFIED") -> dict:
        return self._request(
            "POST",
            "/instruments/search",
            {
                "query": query,
                "instrument_kind": instrument_kind,
                "api_trade_available_flag": trade_available_only,
            },
        )

    def list_instruments(self, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> dict: return self._request("POST", "/instruments/list", {"instrument_kind": instrument_kind, "api_trade_available_flag": trade_available_only})
    def get_instrument(self, instrument_id: str) -> dict: return self._request("POST", "/instruments/get", {"instrument_id": instrument_id})
    def get_indicatives(self) -> dict: return self._request("POST", "/instruments/indicatives", {})
    def get_last_prices(self, instrument_ids: list[str]) -> dict: return self._request("POST", "/market/last-prices", {"instrument_ids": instrument_ids})
    def get_close_prices(self, instrument_ids: list[str]) -> dict: return self._request("POST", "/market/close-prices", {"instrument_ids": instrument_ids})
    def get_candles(self, instrument_id: str, start: Any, end: Any, interval: str = "CANDLE_INTERVAL_DAY", limit: int = 2400) -> dict:
        """Return historical candles without changing the requested time window."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        return self._request("POST", "/market/candles", {"instrument_id": str(instrument_id), "from": start.isoformat() if hasattr(start, "isoformat") else str(start), "to": end.isoformat() if hasattr(end, "isoformat") else str(end), "interval": str(interval), "limit": int(limit)})
    def get_trading_status(self, instrument_id: str) -> dict: return self._request("POST", "/market/trading-status", {"instrument_id": instrument_id})
    def get_trading_statuses(self, instrument_ids: list[str]) -> dict: return self._request("POST", "/market/trading-statuses", {"instrument_ids": instrument_ids})
    def get_orders(self, account_id: str) -> dict: return self._request("POST", "/orders", {"account_id": account_id})
    def get_order_state(self, account_id: str, order_id: str) -> dict: return self._request("POST", "/orders/state", {"account_id": account_id, "order_id": order_id})
    def get_order_price(self, account_id: str, instrument_id: str, price: Any, direction: str, quantity: int) -> dict: return self._request("POST", "/orders/price", {"account_id": account_id, "instrument_id": instrument_id, "price": self._quotation_payload(price), "direction": direction, "quantity": quantity})
    def get_max_lots(self, account_id: str, instrument_id: str, price: Any) -> dict: return self._request("POST", "/orders/max-lots", {"account_id": account_id, "instrument_id": instrument_id, "price": self._quotation_payload(price)})
    def get_operations(self, account_id: str, limit: int = 1000) -> dict: return self._request("POST", "/operations", {"account_id": account_id, "limit": limit})

    @staticmethod
    def _quotation_payload(value: Any) -> dict | None:
        if value is None:
            return None
        if isinstance(value, dict) and ("units" in value or "nano" in value):
            return {"units": str(value.get("units", 0)), "nano": int(value.get("nano", 0))}
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        whole = int(amount)
        nano = int((amount - Decimal(whole)) * Decimal("1000000000"))
        return {"units": str(whole), "nano": nano}
