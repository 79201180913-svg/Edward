from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from tkinter import messagebox, simpledialog, ttk

from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType


def field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def items(response: Any, *names: str) -> list[Any]:
    if isinstance(response, list):
        return response
    for name in names:
        value = field(response, name, None)
        if value is not None:
            return list(value or [])
    return []


def decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def human_status(value: Any) -> str:
    raw = str(value or "").upper()
    mapping = {
        "EXECUTION_REPORT_STATUS_NEW": "Новая",
        "EXECUTION_REPORT_STATUS_FILL": "Исполнена",
        "EXECUTION_REPORT_STATUS_PARTIALLYFILL": "Частично исполнена",
        "EXECUTION_REPORT_STATUS_PARTIALLY_FILLED": "Частично исполнена",
        "EXECUTION_REPORT_STATUS_CANCELLED": "Отменена",
        "EXECUTION_REPORT_STATUS_REJECTED": "Отклонена",
        "EXECUTION_REPORT_STATUS_PENDING_CANCEL": "Отмена ожидается",
        "EXECUTION_REPORT_STATUS_PENDING_REPLACE": "Изменение ожидается",
        "EXECUTION_REPORT_STATUS_PENDING": "Ожидает исполнения",
        "EXECUTION_REPORT_STATUS_UNSPECIFIED": "Неизвестно",
    }
    if raw in mapping:
        return mapping[raw]
    if "PART" in raw and "FILL" in raw:
        return "Частично исполнена"
    if "FILL" in raw:
        return "Исполнена"
    if "CANCEL" in raw:
        return "Отменена"
    if "REJECT" in raw:
        return "Отклонена"
    if "PENDING" in raw:
        return "Ожидает исполнения"
    if raw in {"NEW", "OPEN", "ACTIVE"}:
        return "Новая"
    return str(value or "—")


def human_direction(value: Any) -> str:
    raw = str(value or "").upper()
    if "BUY" in raw:
        return "Покупка"
    if "SELL" in raw:
        return "Продажа"
    return str(value or "—")


def human_order_type(value: Any) -> str:
    raw = str(value or "").upper()
    if "MARKET" in raw:
        return "Рыночная"
    if "BESTPRICE" in raw or "BEST_PRICE" in raw:
        return "Лучшая цена"
    if "LIMIT" in raw:
        return "Лимитная"
    return str(value or "—")


def remaining_quantity(requested: Any, executed: Any) -> Decimal:
    result = decimal(requested) - decimal(executed)
    return max(result, Decimal("0"))


def order_row(order: Any) -> dict[str, Any]:
    requested = field(order, "lots_requested", field(order, "quantity", field(order, "quantity_requested", 0)))
    executed = field(order, "lots_executed", field(order, "quantity_executed", field(order, "executed_quantity", 0)))
    status = field(order, "execution_report_status", field(order, "status", ""))
    direction = field(order, "direction", field(order, "side", ""))
    order_type = field(order, "order_type", field(order, "type", ""))
    price = field(order, "initial_security_price", field(order, "price", field(order, "requested_price", "")))
    return {
        "order_id": str(field(order, "order_id", field(order, "id", "")) or ""),
        "ticker": str(field(order, "ticker", "") or ""),
        "instrument_uid": str(field(order, "instrument_uid", field(order, "uid", "")) or ""),
        "figi": str(field(order, "figi", "") or ""),
        "direction_raw": str(direction or ""),
        "direction": human_direction(direction),
        "order_type_raw": str(order_type or ""),
        "order_type": human_order_type(order_type),
        "requested": decimal(requested),
        "executed": decimal(executed),
        "remaining": remaining_quantity(requested, executed),
        "status_raw": str(status or ""),
        "status": human_status(status),
        "price": decimal(price) if price not in (None, "") else None,
        "raw": order,
    }


def _status_allows_cancel(row: dict[str, Any]) -> bool:
    return row["status"] in {"Новая", "Ожидает исполнения", "Частично исполнена", "Отмена ожидается"}


def _status_allows_replace(row: dict[str, Any]) -> bool:
    return row["status"] in {"Новая", "Ожидает исполнения", "Частично исполнена"}


def install(app_class: type[Any]) -> None:
    original = getattr(app_class, "_page_orders", None)
    if original is None or getattr(original, "_orders_page_v03_wrapped", False):
        return

    def page_orders(self: Any) -> None:
        ttk.Label(self.content, text="Заявки", style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        account_id = self._require_account()
        if not account_id:
            return

        raw_orders = items(self.client.get_orders(account_id), "orders", "items")
        rows = [order_row(order) for order in raw_orders]

        summary = ttk.Frame(self.content)
        summary.pack(fill="x", pady=(0, 10))
        active = sum(1 for row in rows if _status_allows_cancel(row))
        pending = sum(1 for row in rows if row["status"] == "Ожидает исполнения")
        partial = sum(1 for row in rows if row["status"] == "Частично исполнена")
        ttk.Label(summary, text=f"Всего заявок: {len(rows)} | Активных: {active} | Ожидают: {pending} | Частично исполнено: {partial}").pack(anchor="w")

        frame = ttk.Frame(self.content)
        frame.pack(fill="both", expand=True)
        columns = ("ticker", "direction", "order_type", "requested", "executed", "remaining", "price", "status", "order_id", "instrument_uid")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "ticker": ("Тикер", 110),
            "direction": ("Направление", 110),
            "order_type": ("Тип", 110),
            "requested": ("Запрошено", 100),
            "executed": ("Исполнено", 100),
            "remaining": ("Осталось", 100),
            "price": ("Цена", 110),
            "status": ("Статус", 175),
            "order_id": ("", 0),
            "instrument_uid": ("", 0),
        }
        for column in columns:
            title, width = headings[column]
            tree.heading(column, text=title)
            tree.column(column, width=width, minwidth=0 if width == 0 else 40, stretch=width > 0, anchor="e" if column in {"requested", "executed", "remaining", "price"} else "w")
        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scroll.set)
        self._orders_tree = tree
        self._orders_rows = {}

        for index, row in enumerate(rows):
            values = (
                row["ticker"],
                row["direction"],
                row["order_type"],
                f"{row['requested']:.0f}",
                f"{row['executed']:.0f}",
                f"{row['remaining']:.0f}",
                "—" if row["price"] is None else f"{row['price']:.4f}",
                row["status"],
                row["order_id"],
                row["instrument_uid"],
            )
            iid = tree.insert("", "end", values=values)
            self._orders_rows[iid] = row

        tree.bind("<Double-1>", lambda _event: _show_details(self, tree))

        actions = ttk.Frame(self.content)
        actions.pack(fill="x", pady=10)
        ttk.Button(actions, text="Открыть", command=lambda: _show_details(self, tree)).pack(side="left")
        ttk.Button(actions, text="Отменить", command=lambda: _cancel(self, tree)).pack(side="left", padx=8)
        ttk.Button(actions, text="Изменить", command=lambda: _replace(self, tree)).pack(side="left")

        ttk.Label(self.content, text="Двойной клик по заявке — подробности.").pack(anchor="w")

    def _selected(app: Any, tree: ttk.Treeview) -> dict[str, Any] | None:
        selection = tree.selection()
        if not selection:
            return None
        return getattr(app, "_orders_rows", {}).get(selection[0])

    def _show_details(app: Any, tree: ttk.Treeview) -> None:
        row = _selected(app, tree)
        if not row:
            return
        detail = tk_text = None
        text = (
            f"Тикер: {row['ticker']}\n"
            f"Направление: {row['direction']}\n"
            f"Тип: {row['order_type']}\n"
            f"Количество: {row['requested']:.0f} лот(ов)\n"
            f"Исполнено: {row['executed']:.0f}\n"
            f"Осталось: {row['remaining']:.0f}\n"
            f"Цена: {'—' if row['price'] is None else row['price']}\n"
            f"Статус: {row['status']}\n"
            f"ID заявки: {row['order_id']}"
        )
        messagebox.showinfo("Заявка", text, parent=app)

    def _cancel(app: Any, tree: ttk.Treeview) -> None:
        row = _selected(app, tree)
        if not row:
            return
        if not _status_allows_cancel(row):
            messagebox.showinfo("Заявка", "Эту заявку сейчас нельзя отменить.", parent=app)
            return
        if not messagebox.askyesno("Отмена заявки", f"Отменить заявку {row['ticker']}?", parent=app):
            return
        try:
            account_id = app._require_account()
            OrderService(app.client).cancel_order(account_id, row["order_id"])
            app.refresh_current()
        except Exception as exc:
            app._show_error(exc, "отмена заявки")

    def _replace(app: Any, tree: ttk.Treeview) -> None:
        row = _selected(app, tree)
        if not row:
            return
        if not _status_allows_replace(row):
            messagebox.showinfo("Заявка", "Эту заявку сейчас нельзя изменить.", parent=app)
            return

        account_id = app._require_account()
        if not account_id:
            return
        quantity = simpledialog.askinteger(
            "Изменение заявки",
            "Новое количество лот(ов):",
            initialvalue=max(1, int(row["remaining"] or row["requested"])),
            minvalue=1,
            parent=app,
        )
        if quantity is None:
            return

        try:
            side = OrderSide.BUY if row["direction_raw"].upper() == "BUY" else OrderSide.SELL
            order_type_raw = row["order_type_raw"].upper()
            if "MARKET" in order_type_raw:
                order_type = OrderType.MARKET
                price = None
            elif "BESTPRICE" in order_type_raw or "BEST_PRICE" in order_type_raw:
                order_type = OrderType.BESTPRICE
                price = None
            else:
                order_type = OrderType.LIMIT
                default = "" if row["price"] is None else str(row["price"])
                entered = simpledialog.askstring("Изменение заявки", "Новая цена:", initialvalue=default, parent=app)
                if entered is None:
                    return
                price = Decimal(entered.replace(",", "."))
                if price <= 0:
                    raise ValueError("Цена должна быть больше нуля.")

            request = OrderRequest(
                account_id=account_id,
                instrument_uid=row["instrument_uid"],
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            )
            OrderService(app.client).replace_order(account_id, row["order_id"], request)
            app.refresh_current()
        except Exception as exc:
            app._show_error(exc, "изменение заявки")

    app_class._page_orders = page_orders
    app_class._orders_page_v03_wrapped = True
