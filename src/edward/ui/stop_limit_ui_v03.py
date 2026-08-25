from __future__ import annotations

from decimal import Decimal
from tkinter import messagebox, simpledialog, ttk
from typing import Any

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


def install_stop_limit_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_stop_limit_ui_v03_installed", False):
        return

    original_page = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        original_page(self)
        detail = getattr(self, "instrument_detail", None)
        if not detail:
            return
        uid = str(detail.get("instrument_uid", detail.get("uid", "")))
        position = _position(self, uid)
        if position is None or _decimal(_field(position, "balance", 0)) == 0:
            return

        frame = ttk.LabelFrame(self.content, text="Стоп-лимит", padding=10)
        frame.pack(fill="x", pady=(10, 0))
        ttk.Label(
            frame,
            text="После активации выставится лимитная заявка по указанной цене.",
        ).pack(anchor="w")
        ttk.Button(
            frame,
            text="Установить стоп-лимит",
            command=lambda: _create(self, uid, int(abs(_decimal(_field(position, "balance", 0))))),
        ).pack(anchor="w", pady=(8, 0))

    def _create(app: Any, uid: str, quantity: int) -> None:
        try:
            prices = _items(app.client.get_last_prices([uid]), "last_prices")
            current = _decimal(_field(prices[0], "price"))
        except Exception:
            current = _decimal(getattr(app, "instrument_detail", {}).get("last_price"))
        if current <= 0:
            messagebox.showerror("Стоп-лимит", "Не удалось получить текущую цену инструмента.")
            return

        position = _position(app, uid)
        balance = _decimal(_field(position, "balance", 0)) if position is not None else Decimal("0")
        if balance == 0:
            messagebox.showerror("Стоп-лимит", "Открытая позиция отсутствует.")
            return

        long_position = balance > 0
        side = StopOrderSide.SELL if long_position else StopOrderSide.BUY
        raw_stop = simpledialog.askstring(
            "Стоп-лимит",
            f"Цена активации.\nТекущая цена: {current}",
            parent=app,
        )
        if raw_stop is None:
            return
        raw_limit = simpledialog.askstring(
            "Стоп-лимит",
            "Лимитная цена после активации:",
            parent=app,
        )
        if raw_limit is None:
            return
        try:
            stop_price = Decimal(raw_stop.replace(",", "."))
            limit_price = Decimal(raw_limit.replace(",", "."))
        except Exception:
            messagebox.showerror("Стоп-лимит", "Введите корректные цены.")
            return
        if stop_price <= 0 or limit_price <= 0:
            messagebox.showerror("Стоп-лимит", "Цены должны быть больше 0.")
            return

        if long_position:
            if stop_price >= current:
                messagebox.showerror("Стоп-лимит", "Для позиции BUY цена активации продажи должна быть ниже текущей цены.")
                return
            if limit_price > stop_price:
                messagebox.showerror("Стоп-лимит", "Для продажи лимитная цена должна быть не выше цены активации.")
                return
        else:
            if stop_price <= current:
                messagebox.showerror("Стоп-лимит", "Для позиции SELL цена активации покупки должна быть выше текущей цены.")
                return
            if limit_price < stop_price:
                messagebox.showerror("Стоп-лимит", "Для покупки лимитная цена должна быть не ниже цены активации.")
                return

        request = StopOrderRequest(
            account_id=app.context.require_account_id(),
            instrument_uid=uid,
            side=side,
            kind=StopOrderKind.STOP_LIMIT,
            quantity=quantity,
            stop_price=stop_price,
            price=limit_price,
        )
        try:
            result = StopOrderService(app.client).create_protection(request)
            messagebox.showinfo(
                "Стоп-лимит",
                f"Заявка создана.\nID: {_field(result, 'stop_order_id', '')}",
            )
            app.show_page("instrument")
        except Exception as exc:
            messagebox.showerror("Ошибка стоп-лимит", str(exc))

    app_class._page_instrument = page_instrument
    app_class._stop_limit_ui_v03_installed = True
