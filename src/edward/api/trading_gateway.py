from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edward.config.settings import Environment, Settings
from edward.domain import Order
from edward.services.order_service import OrderSide, OrderType


@dataclass(frozen=True, slots=True)
class OrderRequest:
    account_id: str
    instrument_uid: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    price: Decimal | None = None
    request_id: str = ""


@dataclass(frozen=True, slots=True)
class StopOrderRequest:
    account_id: str
    instrument_uid: str
    side: OrderSide
    quantity: int
    stop_price: Decimal
    price: Decimal | None = None
    stop_order_type: str = "STOP_LOSS"
    expiration_type: str = "GOOD_TILL_CANCEL"
    request_id: str = ""


class TradingGateway(ABC):
    @abstractmethod
    def place_order(self, request: OrderRequest) -> Order: raise NotImplementedError

    @abstractmethod
    def cancel_order(self, account_id: str, order_id: str) -> None: raise NotImplementedError

    @abstractmethod
    def place_stop_order(self, request: StopOrderRequest) -> Any: raise NotImplementedError

    @abstractmethod
    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> None: raise NotImplementedError


class SandboxTradingGateway(TradingGateway):
    """Sandbox gateway boundary. Concrete SDK/HTTP adapter is injected by the application."""

    def place_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError("Sandbox order adapter is not configured")

    def cancel_order(self, account_id: str, order_id: str) -> None:
        raise NotImplementedError("Sandbox cancel adapter is not configured")

    def place_stop_order(self, request: StopOrderRequest) -> Any:
        raise NotImplementedError("Sandbox stop-order adapter is not configured")

    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> None:
        raise NotImplementedError("Sandbox stop-order adapter is not configured")


class ProductionTradingGateway(TradingGateway):
    def __init__(self, settings: Settings) -> None:
        if settings.environment is not Environment.PRODUCTION:
            raise RuntimeError("Production gateway requires production environment")

    def place_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError("Production order adapter is not configured")

    def cancel_order(self, account_id: str, order_id: str) -> None:
        raise NotImplementedError("Production cancel adapter is not configured")

    def place_stop_order(self, request: StopOrderRequest) -> Any:
        raise NotImplementedError("Production stop-order adapter is not configured")

    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> None:
        raise NotImplementedError("Production stop-order adapter is not configured")
