from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from tkinter import ttk
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

    def _decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, dict) and ("units" in value or "nano" in value):
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _decimal_text(value: Any) -> str:
        try:
            return app_class._money(value)
        except Exception:
            return str(value or "")

    def _current_rub_balance(self: Any, account_id: str) -> Decimal:
        """Read the current account RUB balance from the same source as the active environment."""
        try:
            positions = self.client.get_sandbox_positions(account_id)
            money = self._items(positions, "money")
            total = Decimal("0")
            for position in money:
                if str(self._field(position, "currency", "")).upper() == "RUB":
                    total += _decimal(self._field(position, "available", 0))
            return total
        except Exception:
            positions = self.client.get_positions(account_id)
            money = self._items(positions, "money")
            total = Decimal("0")
            for position in money:
                if str(self._field(position, "currency", "")).upper() == "RUB":
                    total += _decimal(self._field(position, "available", 0))
            return total

    def _history_clipboard_text(self: Any, tree: Any, selected_only: bool = False) -> str:
        """Build tab-separated text suitable for Excel and other spreadsheets."""
        columns = tuple(tree["columns"])
        header = [str(tree.heading(column, "text")) for column in columns]
        rows = tree.selection() if selected_only else tree.get_children("")
        lines = ["\t".join(header)]
        for item_id in rows:
            values = tree.item(item_id, "values")
            lines.append("\t".join(str(value) for value in values))
        return "\n".join(lines)

    def _copy_history(self: Any, tree: Any, selected_only: bool = False) -> None:
        rows = tree.selection() if selected_only else tree.get_children("")
        if not rows:
            self.status_var.set("Нет операций для копирования.")
            return
        text = _history_clipboard_text(self, tree, selected_only=selected_only)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        count = len(rows)
        scope = "выбранных операций" if selected_only else "операций"
        self.status_var.set(f"Скопировано: {count} {scope}.")

    def _page_history(self: Any) -> None:
        ttk.Label(self.content, text="История операций", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        aid = self._require_account()
        if not aid:
            return

        active_account = getattr(self.context, "active_account", None)
        account_name = getattr(active_account, "name", "") if active_account else ""
        account_display = account_name or aid

        try:
            current_balance = _current_rub_balance(self, aid)
        except Exception as exc:
            current_balance = Decimal("0")
            self.status_var.set(f"Не удалось получить текущий баланс: {exc}")

        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Обновить историю", command=self.refresh_current).pack(side="left")
        ttk.Button(toolbar, text="Копировать всю историю", command=lambda: _copy_history(self, tree, False)).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Копировать выбранное", command=lambda: _copy_history(self, tree, True)).pack(side="left", padx=(8, 0))
        ttk.Label(
            toolbar,
            text=f"Счёт: {account_display} | Текущий баланс: {_decimal_text(current_balance)} RUB | Статусы: Успех / Ошибка / В процессе",
        ).pack(side="left", padx=15)

        tree = self._tree(
            self.content,
            ("Дата", "Время", "Счёт", "Тип", "Статус", "Сумма", "Валюта", "Текущий баланс", "Инструмент", "Количество", "Операция ID"),
            (100, 85, 270, 170, 110, 130, 80, 140, 140, 100, 360),
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
                    account_display,
                    _operation_name(operation),
                    _status(operation),
                    _decimal_text(money),
                    str(currency).upper(),
                    _decimal_text(current_balance),
                    instrument,
                    quantity,
                    operation_id,
                ),
            )

        for row in self.history.read_all():
            tree.insert(
                "",
                "end",
                values=(
                    row.get("date", ""),
                    row.get("time", ""),
                    row.get("account_id", account_display),
                    row.get("operation", ""),
                    "Успех" if str(row.get("status", "")).upper() == "FILLED" else "В процессе",
                    row.get("amount", ""),
                    row.get("currency", ""),
                    _decimal_text(current_balance),
                    row.get("ticker", ""),
                    row.get("quantity", ""),
                    row.get("order_id", ""),
                ),
            )

    app_class._page_history = _page_history
    app_class._operations_history_installed = True
