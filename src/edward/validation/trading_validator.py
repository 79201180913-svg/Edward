from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from edward.services.order_service import OrderRequest, OrderSide, OrderType
from edward.validation.order_validator import validate_order_request, validate_price_step


@dataclass(frozen=True, slots=True)
class ValidationContext:
    instrument_available: bool
    trading_allowed: bool
    price_increment: Decimal | None = None
    market_price: Decimal | None = None
    available_money: Decimal | None = None
    available_position: int | None = None
    estimated_total: Decimal | None = None
    estimated_commission: Decimal | None = None
    trading_diagnostic: str = ""
    buy_allowed: bool = True
    sell_allowed: bool = True
    schedule_allowed: bool = True
    user_restrictions_allowed: bool = True
    validation_errors: tuple[str, ...] = ()


class TradingDataProvider(Protocol):
    def get_validation_context(self, request: OrderRequest) -> ValidationContext: ...


class TradingValidator:
    """Final pre-trade validation. The provider must fetch fresh API data."""

    def __init__(self, provider: TradingDataProvider) -> None:
        self._provider = provider

    def validate(self, request: OrderRequest) -> ValidationContext:
        validate_order_request(request)
        context = self._provider.get_validation_context(request)

        if not context.instrument_available:
            raise ValueError("Инструмент недоступен для торговли.")
        if not context.trading_allowed:
            detail = f"\n\nДиагностика статуса: {context.trading_diagnostic}" if context.trading_diagnostic else ""
            raise ValueError(f"Торговля сейчас недоступна для выбранного инструмента.{detail}")
        if not context.schedule_allowed:
            raise ValueError("Торговая сессия сейчас не позволяет выполнить операцию.")
        if not context.user_restrictions_allowed:
            raise ValueError("Для счета или пользователя операция недоступна.")
        if request.side is OrderSide.BUY and not context.buy_allowed:
            raise ValueError("Покупка недоступна для выбранного инструмента.")
        if request.side is OrderSide.SELL and not context.sell_allowed:
            raise ValueError("Продажа недоступна для выбранного инструмента.")
        if context.validation_errors:
            raise ValueError("Проверка заявки не пройдена: " + "; ".join(context.validation_errors))

        if request.order_type is OrderType.LIMIT:
            if request.price is None or context.price_increment is None:
                raise ValueError("Недоступны данные для проверки шага цены.")
            validate_price_step(request.price, context.price_increment)

        if request.side is OrderSide.BUY:
            if context.available_money is None or context.estimated_total is None:
                raise ValueError("Недоступны данные для проверки баланса.")
            required = context.estimated_total + (context.estimated_commission or Decimal("0"))
            if context.available_money < required:
                raise ValueError(
                    "Недостаточно доступных денежных средств.\n\n"
                    f"Доступно: {context.available_money}\nТребуется: {required}"
                )

        if request.side is OrderSide.SELL:
            if context.available_position is None:
                raise ValueError("Недоступны данные о доступном количестве позиции.")
            if request.quantity > context.available_position:
                raise ValueError(
                    "Недостаточно доступного количества инструмента для продажи.\n\n"
                    f"Доступно лотов: {context.available_position}\nЗапрошено лотов: {request.quantity}"
                )

        return context
