from __future__ import annotations

from decimal import Decimal
from typing import Any
import tkinter as tk
from tkinter import ttk

from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.validation.trading_validator import TradingValidator


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
        value = _field(response, name, None)
        if value is not None:
            return list(value or [])
    return []


def _fmt(value: Any, places: int = 4) -> str:
    text = f"{_decimal(value):,.{places}f}".replace(",", " ")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _status_text(value: Any) -> str:
    status = str(value or "").upper()
    return {
        "SECURITY_TRADING_STATUS_NORMAL_TRADING": "Торги идут",
        "SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING": "Торги недоступны",
        "SECURITY_TRADING_STATUS_OPENING_PERIOD": "Открытие",
        "SECURITY_TRADING_STATUS_CLOSING_PERIOD": "Закрытие",
        "SECURITY_TRADING_STATUS_BREAK_IN_TRADING": "Перерыв",
        "SECURITY_TRADING_STATUS_SESSION_CLOSED": "Сессия закрыта",
    }.get(status, str(value or "Неизвестно"))


def _card(parent: Any, title: str, value: str, column: int) -> None:
    frame = ttk.Frame(parent, style="Card.TFrame", padding=14)
    frame.grid(row=0, column=column, sticky="nsew", padx=5)
    ttk.Label(frame, text=title, style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(frame, text=value, style="CardValue.TLabel").pack(anchor="w", pady=(7, 0))


def _find_position(app: Any, uid: str) -> Any | None:
    try:
        response = app.client.get_positions(app.context.require_account_id())
    except Exception:
        return None
    for position in _items(response, "securities", "positions"):
        if str(_field(position, "instrument_uid", _field(position, "uid", ""))) == uid:
            return position
    return None


def install_instrument_screen_ux(app_class: type[Any]) -> None:
    if getattr(app_class, "_instrument_screen_ux_v03_installed", False):
        return
    original = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        detail = getattr(self, "instrument_detail", None)
        if not detail:
            original(self)
            return

        uid = str(detail.get("instrument_uid", detail.get("uid", "")))
        try:
            fresh = self.client.get_instrument(uid)
        except Exception:
            fresh = detail
        try:
            prices = _items(self.client.get_last_prices([uid]), "last_prices")
            last_price = _decimal(_field(prices[0], "price")) if prices else _decimal(detail.get("last_price"))
        except Exception:
            last_price = _decimal(detail.get("last_price"))
        try:
            close = _items(self.client.get_close_prices([uid]), "close_prices")
            close_price = _decimal(_field(close[0], "price")) if close else Decimal("0")
        except Exception:
            close_price = Decimal("0")
        try:
            status = self.client.get_trading_status(uid)
        except Exception:
            status = {}

        ticker = _field(fresh, "ticker", detail.get("ticker", ""))
        name = _field(fresh, "name", detail.get("name", ""))
        currency = str(_field(fresh, "currency", detail.get("currency", "")) or "").upper()
        price_step = _field(fresh, "min_price_increment", detail.get("min_price_increment"))
        change = last_price - close_price if close_price else Decimal("0")
        change_pct = change / close_price * Decimal("100") if close_price else Decimal("0")

        self._clear()
        ttk.Button(self.content, text="← К инструментам", command=lambda: self.show_page("instruments")).pack(anchor="w", pady=(0, 8))
        ttk.Label(self.content, text=f"{ticker} — {name}", style="Title.TLabel").pack(anchor="w", pady=(0, 16))

        summary = ttk.Frame(self.content)
        summary.pack(fill="x")
        for col in range(4):
            summary.columnconfigure(col, weight=1)
        _card(summary, "Текущая цена", f"{_fmt(last_price)} {currency}".strip(), 0)
        _card(summary, "Изменение за день", f"{change:+.4f} ({change_pct:+.2f}%) {currency}".strip(), 1)
        _card(summary, "Шаг цены", f"{_fmt(price_step, 8)} {currency}".strip(), 2)
        _card(summary, "Торговый статус", _status_text(_field(status, "trading_status", _field(status, "status", ""))), 3)

        info = ttk.LabelFrame(self.content, text="Информация", padding=10)
        info.pack(fill="x", pady=(18, 8))
        rows = [
            ("Тикер", ticker),
            ("UID", uid),
            ("Валюта", currency),
            ("Тип", detail.get("instrument_kind", "SHARE")),
            ("BUY", "Доступна" if _field(status, "buy_available_flag", detail.get("buy_available", False)) else "Недоступна"),
            ("SELL", "Доступна" if _field(status, "sell_available_flag", detail.get("sell_available", False)) else "Недоступна"),
            ("LIMIT", "Доступен" if _field(status, "limit_order_available_flag", False) else "Недоступен"),
            ("MARKET", "Доступен" if _field(status, "market_order_available_flag", False) else "Недоступен"),
            ("BESTPRICE", "Доступен" if _field(status, "bestprice_order_available_flag", False) else "Недоступен"),
        ]
        for row, (label, value) in enumerate(rows):
            ttk.Label(info, text=label + ":", width=14).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Label(info, text=str(value)).grid(row=row, column=1, sticky="w", pady=2)

        position = _find_position(self, uid)
        if position is not None:
            pf = ttk.LabelFrame(self.content, text="Моя позиция", padding=10)
            pf.pack(fill="x", pady=(4, 8))
            pos_rows = [
                ("Количество", _field(position, "balance", 0)),
                ("Средняя цена", _field(position, "average_position_price", _field(position, "average_price", ""))),
                ("P&L", _field(position, "expected_yield", _field(position, "expected_yield_fifo", ""))),
            ]
            for row, (label, value) in enumerate(pos_rows):
                ttk.Label(pf, text=label + ":", width=14).grid(row=row, column=0, sticky="w", pady=2)
                ttk.Label(pf, text=str(value)).grid(row=row, column=1, sticky="w", pady=2)

        order = ttk.LabelFrame(self.content, text="Быстрая заявка", padding=12)
        order.pack(fill="x", pady=(10, 0))
        side = tk.StringVar(value=OrderSide.BUY.value)
        order_type = tk.StringVar(value="")
        quantity = tk.StringVar(value="1")
        price = tk.StringVar(value=_fmt(last_price, 8))

        ttk.Radiobutton(order, text="Купить", variable=side, value=OrderSide.BUY.value).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ttk.Radiobutton(order, text="Продать", variable=side, value=OrderSide.SELL.value).grid(row=0, column=1, padx=(0, 18), sticky="w")
        ttk.Label(order, text="Тип:").grid(row=0, column=2, padx=(0, 6), sticky="w")

        available_types: list[str] = []
        if _field(status, "limit_order_available_flag", False):
            available_types.append(OrderType.LIMIT.value)
        if _field(status, "market_order_available_flag", False):
            available_types.append(OrderType.MARKET.value)
        if _field(status, "bestprice_order_available_flag", False):
            available_types.append(OrderType.BESTPRICE.value)

        type_box = ttk.Combobox(order, textvariable=order_type, state="readonly", values=available_types, width=12)
        type_box.grid(row=0, column=3, padx=(0, 18), sticky="w")
        if available_types:
            order_type.set(available_types[0])
        else:
            type_box.configure(state="disabled")

        ttk.Label(order, text="Количество лотов:").grid(row=0, column=4, padx=(0, 6), sticky="w")
        ttk.Entry(order, textvariable=quantity, width=10).grid(row=0, column=5, padx=(0, 18), sticky="w")
        ttk.Label(order, text="Цена за 1 шт.:").grid(row=0, column=6, padx=(0, 6), sticky="w")
        price_entry = ttk.Entry(order, textvariable=price, width=12)
        price_entry.grid(row=0, column=7, padx=(0, 18), sticky="w")
        ttk.Button(order, text="Отправить", command=lambda: submit(self, side, order_type, quantity, price)).grid(row=0, column=8, sticky="e")
        order.columnconfigure(8, weight=1)

        def update_price_state(_event: Any = None) -> None:
            if order_type.get() == OrderType.LIMIT.value:
                price_entry.configure(state="normal")
                if not price.get().strip():
                    price.set(_fmt(last_price, 8))
            else:
                price.set("")
                price_entry.configure(state="disabled")

        type_box.bind("<<ComboboxSelected>>", update_price_state)
        update_price_state()

    def submit(self: Any, side: tk.StringVar, order_type: tk.StringVar, quantity: tk.StringVar, price: tk.StringVar) -> None:
        account_id = self._require_account()
        detail = getattr(self, "instrument_detail", None)
        if not account_id or not detail:
            return
        try:
            request_type = OrderType(order_type.get())
            request_price = Decimal(price.get()) if request_type is OrderType.LIMIT else None
            request = OrderRequest(
                account_id=account_id,
                instrument_uid=str(detail.get("instrument_uid", detail.get("uid", ""))),
                side=OrderSide(side.get()),
                order_type=request_type,
                quantity=int(quantity.get()),
                price=request_price,
                instrument_kind=detail.get("instrument_kind", "SHARE"),
            )
            context = TradingValidator(AdapterTradingDataProvider(self.client)).validate(request)
            if not tk.messagebox.askyesno if False else False:
                return
            result = OrderService(self.client).create_order(request)
            tk.messagebox.showinfo("Заявка отправлена", f"Order ID: {_field(result, 'order_id', '')}")
            self.show_page("instrument")
        except Exception as exc:
            # Convert the API/validator failure to a trader-facing message.
            if request_type is OrderType.MARKET:
                message = "Рыночная заявка недоступна для этого инструмента. Выберите LIMIT."
            elif request_type is OrderType.BESTPRICE:
                message = "Заявка по лучшей цене недоступна для этого инструмента. Выберите LIMIT."
            else:
                message = str(exc)
            tk.messagebox.showerror("Ошибка заявки", message)

    app_class._page_instrument = page_instrument
    app_class._instrument_screen_ux_v03_installed = True
