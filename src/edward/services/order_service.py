from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4
from typing import Any, Protocol


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    account_id: str
    instrument_uid: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Decimal | None = None
    stop_price: Decimal | None = None
    request_id: str = ""
    instrument_kind: str = "SHARE"

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.price is None:
            raise ValueError("Limit price is required for this order type")
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError("Stop price is required for this order type")
        if not self.request_id:
            object.__setattr__(self, "request_id", str(uuid4()))


class OrdersGateway(Protocol):
    def post_order(self, request: OrderRequest) -> Any: ...
    def get_order_state(self, account_id: str, order_id: str) -> Any: ...
    def get_orders(self, account_id: str) -> Any: ...
    def cancel_order(self, account_id: str, order_id: str) -> Any: ...
    def replace_order(self, request: OrderRequest, order_id: str) -> Any: ...
    def get_last_prices(self, instrument_ids: list[str]) -> Any: ...


class OrderService:
    """Application service responsible for all order lifecycle operations."""

    def __init__(self, gateway: OrdersGateway) -> None:
        self._gateway = gateway

    @staticmethod
    def _items(response: Any, name: str) -> list[Any]:
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return list(response.get(name, []) or [])
        return list(getattr(response, name, []) or [])

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, dict) and ("units" in value or "nano" in value):
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def _ensure_market_price(self, request: OrderRequest) -> OrderRequest:
        if request.order_type != OrderType.MARKET or request.price is not None:
            return request

        response = self._gateway.get_last_prices([request.instrument_uid])
        prices = self._items(response, "last_prices")
        if not prices:
            raise RuntimeError("Не удалось получить актуальную цену для рыночной заявки.")

        raw_price = self._field(prices[0], "price", self._field(prices[0], "last_price", None))
        market_price = self._decimal(raw_price)
        if market_price is None or market_price <= 0:
            raise RuntimeError(f"Не удалось получить корректную цену для рыночной заявки: {raw_price!r}")

        return replace(request, price=market_price)

    def create_order(self, request: OrderRequest) -> Any:
        request = self._ensure_market_price(request)
        return self._gateway.post_order(request)

    def get_order_state(self, account_id: str, order_id: str) -> Any:
        return self._gateway.get_order_state(account_id, order_id)

    def get_active_orders(self, account_id: str) -> Any:
        return self._gateway.get_orders(account_id)

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        return self._gateway.cancel_order(account_id, order_id)

    def replace_order(self, account_id: str, order_id: str, request: OrderRequest) -> Any:
        if request.account_id != account_id:
            raise ValueError("Order account does not match active account")
        return self._gateway.replace_order(request, order_id)
