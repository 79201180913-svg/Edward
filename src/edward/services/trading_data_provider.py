from __future__ import annotations

from decimal import Decimal
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.balance_service import BalanceService
from edward.services.order_service import OrderRequest, OrderSide
from edward.validation.trading_validator import ValidationContext


class AdapterTradingDataProvider:
    """Builds last-moment trading validation data from the adapter."""

    def __init__(self, client: TInvestAdapterClient) -> None:
        self._client = client

    def get_validation_context(self, request: OrderRequest) -> ValidationContext:
        instruments = self._items(self._client.find_instrument(request.instrument_uid, False), "instruments")
        instrument = instruments[0] if instruments else {}
        status = self._client.get_trading_status(request.instrument_uid)
        available = bool(self._field(status, "api_trade_available_flag", False))
        current = self._items(self._client.get_last_prices([request.instrument_uid]), "last_prices")
        market_price = self._decimal(self._field(current[0], "price")) if current else None
        increment = self._decimal(self._field(instrument, "min_price_increment"))
        if increment is None:
            increment = self._decimal(self._field(instrument, "min_price_increment_value"))

        positions = self._client.get_positions(request.account_id)
        money = BalanceService.get_money_positions(positions)
        securities = BalanceService.get_security_positions(positions)
        available_money = Decimal("0")
        for item in money:
            if str(self._field(item, "currency", "")).lower() == "rub":
                available_money += self._decimal(self._field(item, "available"))

        available_position = None
        for item in securities:
            uid = str(self._field(item, "instrument_uid", self._field(item, "figi", "")))
            if uid == request.instrument_uid:
                balance = self._decimal(self._field(item, "balance"))
                blocked = self._decimal(self._field(item, "blocked"))
                available_position = max(0, int(balance - blocked))
                break

        unit_price = request.price or market_price
        estimated_total = unit_price * request.quantity if unit_price is not None else None
        return ValidationContext(
            instrument_available=bool(instrument),
            trading_allowed=available,
            price_increment=increment,
            market_price=market_price,
            available_money=available_money if request.side == OrderSide.BUY else None,
            available_position=available_position if request.side == OrderSide.SELL else None,
            estimated_total=estimated_total,
            estimated_commission=Decimal("0"),
        )

    @staticmethod
    def _items(response: Any, name: str) -> list[Any]:
        if isinstance(response, list):
            return response
        value = response.get(name, []) if isinstance(response, dict) else getattr(response, name, [])
        return list(value or [])

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, dict) and ("units" in value or "nano" in value):
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        try:
            return Decimal(str(value))
        except Exception:
            return None
