from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any


@dataclass
class TInvestAdapterClient:
    base_url: str = "http://127.0.0.1:8765"
    timeout: float = 20.0

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(f"{self.base_url}{path}", data=data, method=method, headers={"Content-Type": "application/json"})
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

    def health(self) -> dict: return self._request("GET", "/health")
    def get_accounts(self) -> dict: return self._request("POST", "/accounts", {})
    def create_sandbox_account(self, name: str | None = None) -> dict: return self._request("POST", "/accounts/create", {"name": name} if name else {})
    def close_sandbox_account(self, account_id: str) -> dict: return self._request("POST", "/accounts/close", {"account_id": account_id})
    def sandbox_pay_in(self, account_id: str, amount: Any) -> dict: return self._request("POST", "/accounts/pay-in", {"account_id": account_id, "amount": str(amount)})
    def get_sandbox_positions(self, account_id: str) -> dict: return self._request("POST", "/accounts/sandbox-positions", {"account_id": account_id})
    def get_sandbox_portfolio(self, account_id: str) -> dict: return self._request("POST", "/accounts/sandbox-portfolio", {"account_id": account_id})
    def get_sandbox_withdraw_limits(self, account_id: str) -> dict: return self._request("POST", "/accounts/sandbox-withdraw-limits", {"account_id": account_id})
    def get_portfolio(self, account_id: str) -> dict:
        if str(self.health().get("environment", "")).lower() == "sandbox":
            return self.get_sandbox_portfolio(account_id)
        return self._request("POST", "/portfolio", {"account_id": account_id})

    @staticmethod
    def _money_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, dict):
            if "units" in value or "nano" in value:
                return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
            if "value" in value:
                return TInvestAdapterClient._money_decimal(value["value"])
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def get_positions(self, account_id: str) -> dict:
        if str(self.health().get("environment", "")).lower() != "sandbox":
            return self._request("POST", "/positions", {"account_id": account_id})

        positions = self.get_sandbox_positions(account_id)
        portfolio = self.get_sandbox_portfolio(account_id)

        cash_value = portfolio.get("total_amount_currencies") if isinstance(portfolio, dict) else None
        cash_amount = self._money_decimal(cash_value) if cash_value is not None else None

        # Sandbox cash is returned by GetSandboxPositions as PositionsMoney.
        # Current API schema uses available_value / blocked_value.
        if cash_amount is None or cash_amount == 0:
            raw_money = positions.get("money", []) if isinstance(positions, dict) else []
            total_available = Decimal("0")
            found_rub = False
            for item in raw_money:
                if str(item.get("currency", "")).upper() != "RUB":
                    continue
                found_rub = True
                available = item.get("available_value", item.get("available", 0))
                total_available += self._money_decimal(available)
            if found_rub:
                cash_amount = total_available

        # A newly created sandbox account can have no money position yet.
        if cash_amount is None:
            cash_amount = Decimal("0")

        whole = cash_amount.quantize(Decimal("1"))
        nano = int((cash_amount - whole) * Decimal("1000000000"))
        result = dict(positions)
        result["money"] = [{
            "currency": "RUB",
            "available": {"units": str(whole), "nano": nano},
            "available_value": {"units": str(whole), "nano": nano},
            "blocked": {"units": "0", "nano": 0},
            "blocked_value": {"units": "0", "nano": 0},
        }]
        return result

    def find_instrument(self, query: str, trade_available_only: bool = True) -> dict: return self._request("POST", "/instruments/search", {"query": query, "api_trade_available_flag": trade_available_only})
    def list_instruments(self, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> dict: return self._request("POST", "/instruments/list", {"instrument_kind": instrument_kind, "api_trade_available_flag": trade_available_only})
    def get_instrument(self, instrument_id: str) -> dict: return self._request("POST", "/instruments/get", {"instrument_id": instrument_id})
    def get_last_prices(self, instrument_ids: list[str]) -> dict: return self._request("POST", "/market/last-prices", {"instrument_ids": instrument_ids})
    def get_trading_status(self, instrument_id: str) -> dict: return self._request("POST", "/market/trading-status", {"instrument_id": instrument_id})
    def get_trading_statuses(self, instrument_ids: list[str]) -> dict: return self._request("POST", "/market/trading-statuses", {"instrument_ids": instrument_ids})
    def get_orders(self, account_id: str) -> dict: return self._request("POST", "/orders", {"account_id": account_id})
    def get_order_state(self, account_id: str, order_id: str) -> dict: return self._request("POST", "/orders/state", {"account_id": account_id, "order_id": order_id})
    def get_order_price(self, account_id: str, instrument_id: str, price: Any, direction: str, quantity: int) -> dict:
        return self._request("POST", "/orders/price", {"account_id": account_id, "instrument_id": instrument_id, "price": price, "direction": direction, "quantity": quantity})
    def get_max_lots(self, account_id: str, instrument_id: str, price: Any) -> dict: return self._request("POST", "/orders/max-lots", {"account_id": account_id, "instrument_id": instrument_id, "price": price})
    def get_operations(self, account_id: str, limit: int = 1000) -> dict: return self._request("POST", "/operations", {"account_id": account_id, "limit": limit})

    @staticmethod
    def _order_payload(request: Any) -> dict:
        return {"quantity": int(getattr(request, "quantity")), "direction": getattr(getattr(request, "side"), "value", getattr(request, "side")), "account_id": str(getattr(request, "account_id")), "order_type": getattr(getattr(request, "order_type"), "value", getattr(request, "order_type")), "instrument_uid": str(getattr(request, "instrument_uid")), "request_id": str(getattr(request, "request_id")), "price": str(getattr(request, "price")) if getattr(request, "price", None) is not None else None, "stop_price": str(getattr(request, "stop_price")) if getattr(request, "stop_price", None) is not None else None, "time_in_force": getattr(getattr(request, "time_in_force", None), "value", getattr(request, "time_in_force", "DAY"))}

    def post_order(self, request: Any) -> dict: return self._request("POST", "/orders/create", self._order_payload(request))
    def cancel_order(self, account_id: str, order_id: str) -> dict: return self._request("POST", "/orders/cancel", {"account_id": account_id, "order_id": order_id})
    def replace_order(self, request: Any, order_id: str) -> dict:
        payload = self._order_payload(request); payload["order_id"] = order_id
        return self._request("POST", "/orders/replace", payload)
