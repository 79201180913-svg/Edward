from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

HEADERS = [
    'date', 'time', 'account_id', 'order_id', 'instrument_uid', 'FIGI', 'ticker', 'name',
    'operation', 'quantity', 'order_type', 'execution_price', 'amount', 'commission',
    'currency', 'status'
]


@dataclass(frozen=True, slots=True)
class TradeRecord:
    account_id: str
    order_id: str
    instrument_uid: str
    operation: str
    quantity: int
    order_type: str
    execution_price: Decimal | None
    amount: Decimal | None
    commission: Decimal | None
    currency: str
    status: str
    figi: str = ''
    ticker: str = ''
    name: str = ''
    executed_at: datetime | None = None


class TradingHistoryRepository:
    def __init__(self, path: str | Path = 'data/trading_history.xlsx') -> None:
        self.path = Path(path)

    def save_completed(self, record: TradeRecord) -> None:
        if record.status != 'FILLED':
            raise ValueError('save_completed accepts only FILLED operations')
        self.save(record)

    def save(self, record: TradeRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            workbook = load_workbook(self.path)
            sheet = workbook.active
            self._ensure_headers(sheet)
        else:
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = 'Trades'
            sheet.append(HEADERS)

        if self._contains_order(sheet, record.order_id):
            workbook.close()
            return

        timestamp = record.executed_at or datetime.now(timezone.utc)
        data = {
            'date': timestamp.date().isoformat(),
            'time': timestamp.time().isoformat(timespec='seconds'),
            'account_id': record.account_id,
            'order_id': record.order_id,
            'instrument_uid': record.instrument_uid,
            'FIGI': record.figi,
            'ticker': record.ticker,
            'name': record.name,
            'operation': record.operation,
            'quantity': record.quantity,
            'order_type': record.order_type,
            'execution_price': self._decimal(record.execution_price),
            'amount': self._decimal(record.amount),
            'commission': self._decimal(record.commission),
            'currency': record.currency,
            'status': record.status,
        }
        sheet.append([data[h] for h in HEADERS])
        workbook.save(self.path)
        workbook.close()

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        workbook = load_workbook(self.path, read_only=True, data_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
        workbook.close()
        return [dict(zip(HEADERS, row)) for row in rows[1:]] if rows else []

    @staticmethod
    def _decimal(value: Decimal | None) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _ensure_headers(sheet: Any) -> None:
        existing = [cell.value for cell in sheet[1]]
        if existing != HEADERS:
            for index, header in enumerate(HEADERS, start=1):
                sheet.cell(row=1, column=index).value = header

    @staticmethod
    def _contains_order(sheet: Any, order_id: str) -> bool:
        column = HEADERS.index('order_id') + 1
        return any(
            cell.value == order_id
            for cell in next(sheet.iter_cols(min_col=column, max_col=column, min_row=2, values_only=False))
        )
