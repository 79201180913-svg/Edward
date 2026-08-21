from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from tkinter import messagebox, ttk
from typing import Any

from edward.services.balance_service import BalanceService


_OPERATION_STATE = {
    0: "Не определён",
    1: "Успех",      # OPERATION_STATE_EXECUTED
    2: "Ошибка",     # OPERATION_STATE_CANCELED
    3: "В процессе", # OPERATION_STATE_PROGRESS
}

_OPERATION_TYPES = {
    1: "Пополнение",      # INPUT
    15: "Покупка",        # BUY
    16: "Покупка",        # BUY_CARD
    19: "Комиссия",       # BROKER_FEE
    22: "Продажа",        # SELL
    70: "Фандинг",        # FUNDING
}


def install_operations_history_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_operations_history_installed", False):
        return

    def _status(value: Any) -> str:
        state = app_class._field(value, "state", "")
        status = app_class._field(value, "status", app_class._field(value, "execution_report_status", ""))
        if isinstance(state, int):
            return _OPERATION_STATE.get(state, "В процессе")
        state_text = str(state).upper()
        status_text = str(status).upper()
        combined = f"{state_text} {status_text}"
        if any(token in combined for token in ("CANCEL", "CANCELED", "REJECT", "ERROR", "FAIL")):
            return "Ошибка"
        if any(token in combined for token in ("EXECUTED", "FILL", "SUCCESS")):
            return "Успех"
        return "В процессе"

    def _operation_name(value: Any) -> str:
        raw = app_class._field(value, "operation_type", app_class._field(value, "type", ""))
        if isinstance(raw, int):
            return _OPERATION_TYPES.get(raw, f"Операция #{raw}")
        text = str(raw).upper()
        mapping = {
            "OPERATION_TYPE_INPUT": "Пополнение",
            "OPERATION_TYPE_FUNDING": "Фандинг",
            "OPERATION_TYPE_BUY": "Покупка",
            "OPERATION_TYPE_BUY_CARD": "Покупка",
            "OPERATION_TYPE_SELL": "Продажа",
            "OPERATION_TYPE_SELL_CARD": "Продажа",
            "OPERATION_TYPE_BROKER_FEE": "Комиссия",
            "OPERATION_TYPE_SERVICE_FEE": "Сервисная комиссия",
        }
        return mapping.get(text, text.replace("OPERATION_TYPE_", "").replace("_", " ").title() or "Операция")

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
        return app_class._money(value)

    def _financial_snapshot(self: Any, account_id: str) -> tuple[Decimal, Decimal]:
        positions = self.client.get_positions(account_id)
        portfolio = self.client.get_portfolio(account_id)
        summary = BalanceService.build_summary(positions, portfolio)
        return summary.available, summary.portfolio_value

    def _copy_rows(self: Any, tree: Any, selected_only: bool = False) -> None:
        items = tree.selection() if selected_only else tree.get_children("")
        columns = [tree.heading(column, "text") for column in tree["columns"]]
        lines = ["\t".join(columns)]
        for item in items:
            lines.append("\t".join(str(value) for value in tree.item(item, "values")))
        if len(lines) <= 1:
            messagebox.showinfo("Edward", "Нет строк для копирования.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.update()
        self.status_var.set(f"Скопировано строк: {len(lines) - 1}")

    def _page_history(self: Any) -> None:
        ttk.Label(self.content, text="История операций", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        aid = self._require_account()
        if not aid:
            return

        active_account = getattr(self.context, "active_account", None)
        account_name = getattr(active_account, "name", "") if active_account else ""
        account_display = account_name or aid

        try:
            current_balance, portfolio_value = _financial_snapshot(self, aid)
        except Exception as exc:
            current_balance = Decimal("0")
            portfolio_value = Decimal("0")
            self.status_var.set(f"Не удалось получить финансовое состояние: {exc}")
            print(f"[HISTORY SNAPSHOT ERROR] {type(exc).__name__}: {exc}", flush=True)

        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Обновить историю", command=self.refresh_current).pack(side="left")
        tree = self._tree(
            self.content,
            ("Дата", "Время", "Счёт", "Тип", "Статус", "Сумма", "Валюта", "Текущий баланс", "Стоимость портфеля", "Инструмент", "Количество", "Операция ID"),
            (100, 85, 270, 170, 110, 130, 80, 140, 150, 140, 100, 360),
        )
        ttk.Button(toolbar, text="Копировать всю историю", command=lambda: _copy_rows(self, tree, False)).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Копировать выбранное", command=lambda: _copy_rows(self, tree, True)).pack(side="left")
        ttk.Label(toolbar, text=f"Счёт: {account_display} | Текущий баланс: {_decimal_text(current_balance)} RUB | Стоимость портфеля: {_decimal_text(portfolio_value)} RUB").pack(side="left", padx=15)

        seen_ids: set[str] = set()
        api_count = 0
        try:
            response = self.client.get_operations(aid, 1000)
            operations = self._items(response, "operations", "items")
            api_count = len(operations)
            print(f"[HISTORY API] account_id={aid} operations={api_count}", flush=True)
        except Exception as exc:
            self._show_error(exc, "получение истории операций")
            operations = []

        for operation in operations:
            operation_id = str(self._field(operation, "id", self._field(operation, "operation_id", "")))
            if operation_id:
                seen_ids.add(operation_id)

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
            instrument = self._field(operation, "ticker", self._field(operation, "instrument_uid", self._field(operation, "figi", "")))
            quantity = self._field(operation, "quantity_done", self._field(operation, "quantity", self._field(operation, "lots", "")))
            tree.insert(
                "",
                "end",
                values=(date_text, time_text, account_display, _operation_name(operation), _status(operation), _decimal_text(money), str(currency).upper(), _decimal_text(current_balance), _decimal_text(portfolio_value), instrument, quantity, operation_id),
            )

        local_rows = self.history.read_all()
        local_added = 0
        for row in local_rows:
            operation_id = str(row.get("order_id", ""))
            if operation_id and operation_id in seen_ids:
                continue
            local_added += 1
            local_status = str(row.get("status", "")).upper()
            status_text = "Успех" if local_status == "FILLED" else "Ошибка" if local_status in {"ERROR", "FAILED", "CANCELED", "CANCELLED"} else "В процессе"
            tree.insert(
                "",
                "end",
                values=(row.get("date", ""), row.get("time", ""), row.get("account_id", account_display), row.get("operation", ""), status_text, row.get("amount", ""), row.get("currency", ""), _decimal_text(current_balance), _decimal_text(portfolio_value), row.get("ticker", ""), row.get("quantity", ""), operation_id),
            )

        print(f"[HISTORY] API={api_count} local_added={local_added} total_displayed={api_count + local_added}", flush=True)

    app_class._page_history = _page_history
    app_class._operations_history_installed = True
