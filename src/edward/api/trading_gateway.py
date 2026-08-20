from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from edward.config.settings import Environment, Settings
from edward.domain import Order, OrderSide, OrderType


@dataclass(frozen=True, slots=True)
class OrderRequest:
    account_id: str
    instrument_uid: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType
    price: Decimal | None = None


class TradingGateway(ABC):
    """Application boundary for order submission."""

    @abstractmethod
    def place_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, account_id: str, order_id: str) -> None:
        raise NotImplementedError


class SandboxTradingGateway(TradingGateway):
    """Marker gateway for sandbox trading.

    The actual SDK operations will be implemented behind this boundary.
    """

    def place_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError("Sandbox order adapter is not implemented yet")

    def cancel_order(self, account_id: str, order_id: str) -> None:
        raise NotImplementedError("Sandbox cancel adapter is not implemented yet")


class ProductionTradingGateway(TradingGateway):
    """Explicit production gateway; never selectable from sandbox settings."""

    def __init__(self, settings: Settings) -> None:
        if settings.environment is not Environment.PRODUCTION:
            raise RuntimeError("Production gateway requires production environment")

    def place_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError("Production order adapter is not implemented yet")

    def cancel_order(self, account_id: str, order_id: str) -> None:
        raise NotImplementedError("Production cancel adapter is not implemented yet")
