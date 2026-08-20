from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edward.domain.order_state import OrderSnapshot, OrderStatus
from edward.history.trading_history import TradeRecord, TradingHistoryRepository


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    figi: str = ""
    ticker: str = ""
    name: str = ""
    operation: str = ""
    order_type: str = ""
    currency: str = "RUB"


class ExecutionService:
    """Processes terminal order states and persists only actual executions."""

    def __init__(self, history: TradingHistoryRepository) -> None:
        self._history = history

    def process(self, snapshot: OrderSnapshot, context: ExecutionContext) -> None:
        if snapshot.status is not OrderStatus.FILLED:
            return
        if snapshot.filled_quantity <= 0:
            return

        amount = None
        if snapshot.average_fill_price is not None:
            price = self._to_decimal(snapshot.average_fill_price)
            amount = price * snapshot.filled_quantity
        else:
            price = None

        commission = self._to_decimal(snapshot.commission)
        record = TradeRecord(
            account_id=snapshot.account_id,
            order_id=snapshot.order_id,
            instrument_uid=snapshot.instrument_uid,
            figi=context.figi,
            ticker=context.ticker,
            name=context.name,
            operation=context.operation,
            quantity=snapshot.filled_quantity,
            order_type=context.order_type,
            execution_price=price,
            amount=amount,
            commission=commission,
            currency=context.currency,
            status="FILLED",
            executed_at=snapshot.updated_at,
        )
        self._history.save_completed(record)

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        units = getattr(value, "units", None)
        nano = getattr(value, "nano", None)
        if units is not None and nano is not None:
            return Decimal(units) + Decimal(nano) / Decimal(1_000_000_000)
        return Decimal(str(value))
