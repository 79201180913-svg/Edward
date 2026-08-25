from __future__ import annotations

from decimal import Decimal
from typing import Any
from tkinter import messagebox, simpledialog, ttk

from edward.services.stop_order_service import StopOrderKind, StopOrderRequest, StopOrderService, StopOrderSide


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _items(response: Any, *names: str) -> list[Any]:
    if isinstance(response, list):
        return response
    for name in names:
        value = _field(response, name)
        if value is not None:
            return list(value or [])
    return []


def _position(app: Any, uid: str) -> Any | None:
    try:
        positions = app.client.get_positions(app.context.require_account_id())
    except Exception:
        return None
    for item in _items(positions, "securities", "positions"):
        candidate = str(_field(item, "instrument_uid", _field(item, "uid", "")))
        if candidate == uid:
            return item
    return None


def _instrument_uid(order: Any) -> str:
    return str(_field(order, "instrument_uid", _field(order, "instrument_id", _field(order, "instrumentId", ""))))


def _orders_for_instrument(orders: list[Any], uid: str) -> list[Any]:
    return [order for order in orders if _instrument_uid(order) == str(uid)]


def _kind_label(order: Any) -> str:
    raw = str(_field(order, "order_type", _field(order, "stop_order_type", ""))).upper()
    if "STOP_LIMIT" in raw:
        return "Стоп-лимит"
    if "STOP_LOSS" in raw:
        return "Стоп-лосс"
    return "Тейк-профит"


def install_stop_order_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_stop_order_ui_v03_fixed_installed", False):
        return

    original_page = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        original_page(self)
        _render_protection(self)

    def _render_protection(app: Any) -> None:
        detail = getattr(app, "instrument_detail", None)
        if not detail:
            return
        uid = str(detail.get("instrument_uid", detail.get("uid", "")))
        position = _position(app, uid)
        protection = ttk.LabelFrame(app.content, text="Защита позиции", padding=10)
        protection.pack(fill="x", pady=(10, 0))

        if position is None or _decimal(_field(position, "balance", 0)) == 0:
            ttk.Label(protection, text="Открытой позиции нет. Stop Loss и Take Profit доступны после покупки.").pack(anchor="w")
        else:
            balance = int(abs(_decimal(_field(position, "balance", 0))))
            ttk.Label(protection, text=f"Количество для защиты: {balance} лот(ов)").pack(anchor="w")
            buttons = ttk.Frame(protection)
            buttons.pack(anchor="w", pady=(8, 0))
            ttk.Button(buttons, text="Стоп-лосс", command=lambda: _create(app, StopOrderKind.STOP_LOSS, balance)).pack(side="left")
            ttk.Button(buttons, text="Тейк-профит", command=lambda: _create(app, StopOrderKind.TAKE_PROFIT, balance)).pack(side="left", padx=8)

        ttk.Label(protection, text="Активные защитные заявки", style="Subtitle.TLabel").pack(anchor="w", pady=(12, 4))
        try:
            response = StopOrderService(app.client).get_active(app.context.require_account_id())
            orders = _orders_for_instrument(_items(response, "stop_orders"), uid)
        except Exception as exc:
            ttk.Label(protection, text=f"Не удалось получить список: {exc}").pack(anchor="w")
            return

        if not orders:
            ttk.Label(protection, text="Нет активных защитных заявок для этого инструмента").pack(anchor="w")
            return

        tree = ttk.Treeview(protection, columns=("kind", "side", "qty", "stop", "status", "cancel"), show="headings", height=min(5, len(orders)))
        headings = {"kind": "Тип", "side": "Направление", "qty": "Лоты", "stop": "Цена активации", "status": "Статус", "cancel": ""}
        for key, label in headings.items():
            tree.heading(key, text=label)
        tree.column("cancel", width=80)
        tree.pack(fill="x")
        for order in orders:
            tree.insert("", "end", values=(
                _kind_label(order),
                "BUY" if "BUY" in str(_field(order, "direction", "")) else "SELL",
                _field(order, "lots_requested", ""),
                _decimal(_field(order, "stop_price", 0)),
                _field(order, "status", ""),
                "Отменить",
            ), tags=(str(_field(order, "stop_order_id", "")),))

        def cancel_selected() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Защитная заявка", "Выберите заявку.")
                return
            item = tree.item(selected[0])
            stop_id = item.get("tags", [""])[0]
            if not stop_id:
                return
            if not messagebox.askyesno("Отмена заявки", "Отменить выбранную защитную заявку?"):
                return
            try:
                StopOrderService(app.client).cancel(app.context.require_account_id(), stop_id)
                messagebox.showinfo("Защитная заявка", "Заявка отменена.")
                app.show_page("instrument")
            except Exception as exc:
                messagebox.showerror("Ошибка отмены", str(exc))

        ttk.Button(protection, text="Отменить выбранную", command=cancel_selected).pack(anchor="e", pady=(6, 0))

    def _create(app: Any, kind: StopOrderKind, quantity: int) -> None:
        detail = app.instrument_detail
        uid = str(detail.get("instrument_uid", detail.get("uid", "")))
        try:
            price_items = _items(app.client.get_last_prices([uid]), "last_prices")
            current = _decimal(_field(price_items[0], "price"))
        except Exception:
            current = _decimal(detail.get("last_price"))
        if current <= 0:
            messagebox.showerror("Защитная заявка", "Не удалось получить текущую цену инструмента.")
            return

        label = "Stop Loss" if kind is StopOrderKind.STOP_LOSS else "Take Profit"
        prompt = f"Цена активации {label}.\nТекущая цена: {current}"
        raw = simpledialog.askstring(label, prompt, parent=app)
        if raw is None:
            return
        try:
            stop_price = Decimal(raw.replace(",", "."))
        except Exception:
            messagebox.showerror("Защитная заявка", "Введите корректную цену.")
            return
        if stop_price <= 0:
            messagebox.showerror("Защитная заявка", "Цена должна быть больше 0.")
            return

        position = _position(app, uid)
        balance = _decimal(_field(position, "balance", 0)) if position is not None else Decimal("0")
        if balance == 0:
            messagebox.showerror("Защитная заявка", "Открытая позиция отсутствует.")
            return
        long_position = balance > 0
        if kind is StopOrderKind.STOP_LOSS:
            valid = stop_price < current if long_position else stop_price > current
        else:
            valid = stop_price > current if long_position else stop_price < current
        if not valid:
            direction_word = "ниже" if kind is StopOrderKind.STOP_LOSS and long_position else "выше" if kind is StopOrderKind.STOP_LOSS else "выше" if long_position else "ниже"
            messagebox.showerror("Защитная заявка", f"Для {label} цена активации должна быть {direction_word} текущей цены.")
            return

        side = StopOrderSide.SELL if long_position else StopOrderSide.BUY
        request = StopOrderRequest(
            account_id=app.context.require_account_id(),
            instrument_uid=uid,
            side=side,
            kind=kind,
            quantity=min(quantity, int(abs(balance))),
            stop_price=stop_price,
        )
        try:
            result = StopOrderService(app.client).create_protection(request)
            messagebox.showinfo(label, f"Заявка создана.\nID: {_field(result, 'stop_order_id', '')}")
            app.show_page("instrument")
        except Exception as exc:
            messagebox.showerror(f"Ошибка {label}", str(exc))

    app_class._page_instrument = page_instrument
    app_class._stop_order_ui_v03_fixed_installed = True
