from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def install_operations_history_ui(app_class: type[Any]) -> None:
    """Replace the history page with API operation history and explicit statuses."""
    if getattr(app_class, "_operations_history_installed", False):
        return

    def _status(value: Any) -> str:
        state = str(app_class._field(value, "state", "")).upper()
        status = str(app_class._field(value, "status", app_class._field(value, "execution_report_status", ""))).upper()
        combined = f"{state} {status}"
        if "CANCEL" in combined or "REJECT" in combined or "ERROR" in combined:
            return "Ошибка"
        if "EXECUTED" in combined or "FILL" in combined or "SUCCESS" in combined:
            return "Успех"
        if "PROGRESS" in combined or "NEW" in combined or "PARTIAL" in combined:
            return "В процессе"
        return "В процессе"

    def _operation_name(value: Any) -> str:
        raw = str(app_class._field(value, "operation_type", app_class._field(value, "type", ""))).upper()
        mapping = {
            "OPERATION_TYPE_INPUT": "Пополнение",
            "OPERATION_TYPE_FUNDING": "Пополнение",
            "OPERATION_TYPE_BUY": "Покупка",
            "OPERATION_TYPE_BUY_CARD": "Покупка",
            "OPERATION_TYPE_SELL": "Продажа",
            "OPERATION_TYPE_SELL_CARD": "Продажа",
            "OPERATION_TYPE_BROKER_FEE": "Комиссия",
            "OPERATION_TYPE_SERVICE_FEE": "Сервисная комиссия",
        }
        return mapping.get(raw, raw.replace("OPERATION_TYPE_", "").replace("_", " ").title() or "Операция")

    def _decimal_text(value: Any) -> str:
        try:
            return self._money(value)
        except Exception:
            return str(value or "")

    def _page_history(self: Any) -> None:
        ttk = __import__("tkinter.ttk", fromlist=["ttk"]).ttk
        ttk.Label(self.content, text="История операций", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        aid = self._require_account()
        if not aid:
            return

        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Обновить историю", command=self.refresh_current).pack(side="left")
        ttk.Label(toolbar, text="Статусы: Успех / Ошибка / В процессе").pack(side="left", padx=15)

        tree = self._tree(
            self.content,
            ("Дата", "Время", "Тип", "Статус", "Сумма", "Валюта", "Инструмент", "Количество", "Операция ID"),
            (100, 85, 180, 110, 130, 80, 140, 100, 360),
        )

        try:
            response = self.client.get_operations(aid, 1000)
            operations = self._items(response, "operations", "items")
        except Exception as exc:
            self._show_error(exc, "получение истории операций")
            operations = []

        for operation in operations:
            timestamp = self._field(operation, "date", self._field(operation, "timestamp", self._field(operation, "execution_time", "")))
            date_text = ""
            time_text = ""
            if timestamp:
                text = str(timestamp).replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(text)
                    if dt.tzinfo:
                        dt = dt.astimezone(timezone.utc)
                    date_text = dt.strftime("%d.%m.%Y")
                    time_text = dt.strftime("%H:%M:%S")
                except Exception:
                    parts = str(timestamp).split("T", 1)
                    date_text = parts[0]
                    time_text = parts[1][:8] if len(parts) > 1 else ""

            money = self._field(operation, "payment", self._field(operation, "amount", self._field(operation, "sum", "")))
            currency = self._field(money, "currency", self._field(operation, "currency", "RUB"))
            instrument = self._field(operation, "ticker", self._field(operation, "instrument_uid", ""))
            quantity = self._field(operation, "quantity", self._field(operation, "lots", ""))
            operation_id = self._field(operation, "id", self._field(operation, "operation_id", ""))

            tree.insert(
                "",
                "end",
                values=(
                    date_text,
                    time_text,
                    _operation_name(operation),
                    _status(operation),
                    _decimal_text(money),
                    str(currency).upper(),
                    instrument,
                    quantity,
                    operation_id,
                ),
            )

        # Keep the locally saved completed trades visible as well. They are
        # useful for cross-checking API history and Excel history.
        for row in self.history.read_all():
            tree.insert(
                "",
                "end",
                values=(
                    row.get("date", ""),
                    row.get("time", ""),
                    row.get("operation", ""),
                    "Успех" if str(row.get("status", "")).upper() == "FILLED" else "В процессе",
                    row.get("amount", ""),
                    row.get("currency", ""),
                    row.get("ticker", ""),
                    row.get("quantity", ""),
                    row.get("order_id", ""),
                ),
            )

    app_class._page_history = _page_history
    app_class._operations_history_installed = True
