from __future__ import annotations

from decimal import Decimal
from tkinter import messagebox, ttk
from typing import Any


def _field(value: Any, name: str, default: Any = "") -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _items(response: Any) -> list[Any]:
    if isinstance(response, list):
        return response
    for key in ("stop_orders", "orders", "items"):
        value = _field(response, key, None)
        if value is not None:
            return list(value or [])
    return []


def _decimal(value: Any) -> Decimal:
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _kind(value: Any) -> str:
    raw = str(value or "").upper()
    if "STOP_LIMIT" in raw:
        return "Стоп-лимит"
    if "STOP_LOSS" in raw:
        return "Стоп-лосс"
    if "TAKE_PROFIT" in raw:
        return "Тейк-профит"
    return raw.replace("STOP_ORDER_TYPE_", "") or "Защитная"


def _side(value: Any) -> str:
    raw = str(value or "").upper()
    if "SELL" in raw:
        return "Продажа"
    if "BUY" in raw:
        return "Покупка"
    return raw


def _status(value: Any) -> str:
    raw = str(value or "").upper()
    mapping = {
        "STOP_ORDER_STATUS_ACTIVE": "Активна",
        "STOP_ORDER_STATUS_EXECUTED": "Исполнена",
        "STOP_ORDER_STATUS_CANCELED": "Отменена",
        "STOP_ORDER_STATUS_REJECTED": "Отклонена",
    }
    return mapping.get(raw, raw.replace("STOP_ORDER_STATUS_", "") or "—")


def install_stop_orders_page(app_class: type[Any]) -> None:
    if getattr(app_class, "_stop_orders_page_v03_installed", False):
        return

    original_shell = app_class._shell

    def shell(self: Any) -> None:
        original_shell(self)
        if not any(getattr(child, "cget", lambda *_: "")("text") == "Защитные заявки" for child in self.nav.winfo_children()):
            ttk.Button(self.nav, text="Защитные заявки", style="Nav.TButton", command=lambda: self.show_page("stop_orders")).pack(fill="x", pady=2)

    def page_stop_orders(self: Any) -> None:
        ttk.Label(self.content, text="Защитные заявки", font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(0, 12))
        account_id = self._require_account()
        if not account_id:
            return
        response = self.client.get_stop_orders(account_id)
        orders = _items(response)
        tree = ttk.Treeview(
            self.content,
            columns=("ticker", "kind", "side", "qty", "stop", "price", "status"),
            show="headings",
        )
        headings = {
            "ticker": "Тикер", "kind": "Тип", "side": "Направление", "qty": "Лоты",
            "stop": "Цена активации", "price": "Цена заявки", "status": "Статус",
        }
        widths = {"ticker": 100, "kind": 130, "side": 110, "qty": 90, "stop": 140, "price": 130, "status": 130}
        for key, label in headings.items():
            tree.heading(key, text=label)
            tree.column(key, width=widths[key], anchor="center")
        tree.pack(fill="both", expand=True)
        for order in orders:
            tree.insert("", "end", values=(
                _field(order, "ticker", ""),
                _kind(_field(order, "stop_order_type", _field(order, "order_type", ""))),
                _side(_field(order, "direction", "")),
                _field(order, "lots_requested", _field(order, "quantity", "")),
                _decimal(_field(order, "stop_price", 0)),
                _decimal(_field(order, "price", 0)),
                _status(_field(order, "status", "")),
            ), tags=(str(_field(order, "stop_order_id", _field(order, "id", ""))),))

        actions = ttk.Frame(self.content)
        actions.pack(fill="x", pady=10)

        def cancel_selected() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Защитная заявка", "Выберите заявку.")
                return
            stop_id = tree.item(selected[0]).get("tags", [""])[0]
            if not stop_id:
                return
            if not messagebox.askyesno("Отмена заявки", "Отменить выбранную защитную заявку?"):
                return
            try:
                self.client.cancel_stop_order(account_id, stop_id)
                self.show_page("stop_orders")
            except Exception as exc:
                messagebox.showerror("Ошибка отмены", str(exc))

        ttk.Button(actions, text="Отменить выбранную", command=cancel_selected).pack(side="left")
        ttk.Button(actions, text="Обновить", command=lambda: self.show_page("stop_orders")).pack(side="left", padx=8)
        if not orders:
            ttk.Label(self.content, text="Активных защитных заявок нет.").pack(anchor="w", pady=8)

    app_class._shell = shell
    app_class._page_stop_orders = page_stop_orders
    app_class._stop_orders_page_v03_installed = True
