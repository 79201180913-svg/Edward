from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from tkinter import ttk
from typing import Any


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _items(value: Any, *names: str) -> list[Any]:
    if isinstance(value, list):
        return value
    for name in names:
        raw = _field(value, name, None)
        if raw is not None:
            return list(raw or [])
    return []


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict):
        if "units" in value or "nano" in value:
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        for key in ("value", "amount", "payment"):
            if key in value:
                return _decimal(value[key])
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _money(value: Any) -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ")


def _status(value: Any) -> str:
    text = str(value).upper()
    if any(x in text for x in ("CANCEL", "REJECT", "ERROR", "FAIL")):
        return "Ошибка"
    if any(x in text for x in ("EXECUTED", "FILL", "SUCCESS")):
        return "Успех"
    if text in {"1", "2"}:
        return "Успех" if text == "1" else "Ошибка"
    return "В процессе"


def _operation_type(value: Any) -> str:
    text = str(value).upper()
    mapping = {
        "OPERATION_TYPE_INPUT": "Пополнение",
        "OPERATION_TYPE_FUNDING": "Пополнение",
        "OPERATION_TYPE_BUY": "Покупка",
        "OPERATION_TYPE_BUY_CARD": "Покупка",
        "OPERATION_TYPE_SELL": "Продажа",
        "OPERATION_TYPE_SELL_CARD": "Продажа",
        "OPERATION_TYPE_BROKER_FEE": "Комиссия",
        "OPERATION_TYPE_SERVICE_FEE": "Комиссия",
    }
    if text in mapping:
        return mapping[text]
    if "BUY" in text or "ПОКУП" in text:
        return "Покупка"
    if "SELL" in text or "ПРОДАЖ" in text:
        return "Продажа"
    if "INPUT" in text or "FUNDING" in text or "ПОПОЛ" in text:
        return "Пополнение"
    if text:
        return text.replace("OPERATION_TYPE_", "").replace("_", " ").title()
    return "Операция"


def _timestamp(operation: Any) -> tuple[str, str]:
    raw = _field(operation, "date", _field(operation, "timestamp", _field(operation, "execution_time", "")))
    if not raw:
        return "", ""
    text = str(raw)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%d.%m.%Y"), dt.strftime("%H:%M:%S")
    except Exception:
        parts = text.split("T", 1)
        return parts[0], parts[1][:8] if len(parts) > 1 else ""


def install_final_history_fix(EdwardApp: Any) -> None:
    def _page_history(self: Any) -> None:
        ttk.Label(self.content, text="История операций", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        aid = self._require_account()
        if not aid:
            return

        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Обновить историю", command=self.refresh_current).pack(side="left")

        tree = self._tree(
            self.content,
            ("Дата", "Время", "Счёт", "Тип", "Статус", "Сумма", "Валюта", "Инструмент", "Количество", "Операция ID"),
            (100, 85, 290, 150, 110, 140, 80, 180, 100, 390),
        )

        try:
            response = self.client.get_operations(aid, 1000)
            operations = _items(response, "operations", "items")
            print(f"[HISTORY API] account_id={aid} operations={len(operations)}", flush=True)
        except Exception as exc:
            print(f"[HISTORY API ERROR] account_id={aid} {type(exc).__name__}: {exc}", flush=True)
            operations = []

        seen: set[str] = set()
        for operation in operations:
            operation_id = str(_field(operation, "id", _field(operation, "operation_id", "")) or "")
            if operation_id:
                seen.add(operation_id)
            date_text, time_text = _timestamp(operation)
            money = _field(operation, "payment", _field(operation, "amount", ""))
            currency = str(_field(money, "currency", _field(operation, "currency", "RUB")) or "").upper()
            instrument = str(_field(operation, "ticker", _field(operation, "instrument_uid", _field(operation, "figi", ""))) or "")
            quantity = _field(operation, "quantity_done", _field(operation, "quantity", ""))
            tree.insert("", "end", values=(
                date_text,
                time_text,
                aid,
                _operation_type(_field(operation, "operation_type", _field(operation, "type", ""))),
                _status(_field(operation, "state", _field(operation, "status", ""))),
                _money(money) if money not in (None, "") else "",
                currency,
                instrument,
                quantity,
                operation_id,
            ))

        # Local Edward history remains a supplement for order-level data that
        # can exist before the broker operation becomes visible in API history.
        try:
            local_rows = self.history.read_all()
        except Exception as exc:
            print(f"[HISTORY LOCAL ERROR] account_id={aid} {type(exc).__name__}: {exc}", flush=True)
            local_rows = []

        local_added = 0
        for row in local_rows:
            order_id = str(row.get("order_id", "") or "")
            if order_id and order_id in seen:
                continue
            if str(row.get("account_id", aid)) != aid:
                continue
            local_added += 1
            status = str(row.get("status", "")).upper()
            tree.insert("", "end", values=(
                row.get("date", ""),
                row.get("time", ""),
                aid,
                row.get("operation", "Операция"),
                "Успех" if status == "FILLED" else "Ошибка" if status in {"ERROR", "FAILED", "CANCELLED", "CANCELED"} else "В процессе",
                row.get("amount", ""),
                row.get("currency", ""),
                row.get("ticker", ""),
                row.get("quantity", ""),
                order_id,
            ))

        print(f"[HISTORY] account_id={aid} api={len(operations)} local_added={local_added}", flush=True)

    EdwardApp._page_history = _page_history
