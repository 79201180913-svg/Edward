from __future__ import annotations

from decimal import Decimal
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.validation.trading_validator import TradingValidator


def field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def items(response: Any, *names: str) -> list[Any]:
    if isinstance(response, list):
        return response
    for name in names:
        value = field(response, name, None)
        if value is not None:
            return list(value or [])
    return []


def instrument_detail_from_catalog(detail: dict[str, Any]) -> dict[str, Any]:
    """Return the authoritative instrument attributes already loaded by the catalog."""
    return dict(detail)


def install_instrument_screen(app_class: type[Any]) -> None:
    """Install the instrument detail page without changing the core app file."""
    if getattr(app_class, "_instrument_screen_v03_installed", False):
        return

    original_page = app_class._page_instruments
    original_init = app_class.__init__

    def init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.instrument_detail = None
        self.order_side_v03 = tk.StringVar(value=OrderSide.BUY.value)
        self.order_type_v03 = tk.StringVar(value=OrderType.MARKET.value)
        self.order_quantity_v03 = tk.StringVar(value="1")
        self.order_price_v03 = tk.StringVar(value="")

    def open_detail(self: Any) -> None:
        selection = self.instrument_tree.selection()
        if not selection:
            messagebox.showinfo("Инструмент", "Выберите инструмент.")
            return
        values = self.instrument_tree.item(selection[0]).get("values", [])
        if len(values) < 9:
            return
        self.instrument_detail = {
            "ticker": str(values[0]),
            "name": str(values[1]),
            "currency": str(values[2]),
            "last_price": values[3],
            "min_price_increment": values[4],
            "buy_available": values[5] == "Да",
            "sell_available": values[6] == "Да",
            "api_trade_available": values[7] == "Да",
            "uid": str(values[8]),
            "instrument_uid": str(values[8]),
            "instrument_kind": next((kind for kind, label in INSTRUMENT_KINDS if label == self.kind_var.get()), "SHARE"),
        }
        self.show_page("instrument")

    def page_instruments(self: Any) -> None:
        original_page(self)
        if hasattr(self, "instrument_tree"):
            self.instrument_tree.unbind("<Double-1>")
            self.instrument_tree.bind("<Double-1>", lambda _event: open_detail(self))
            controls = ttk.Frame(self.content)
            controls.pack(fill="x", pady=(8, 0))
            ttk.Button(controls, text="Открыть инструмент", command=lambda: open_detail(self)).pack(side="left")

    def page_instrument(self: Any) -> None:
        if not self.instrument_detail:
            ttk.Label(self.content, text="Инструмент не выбран", style="Title.TLabel").pack(anchor="w")
            ttk.Button(self.content, text="← К инструментам", command=lambda: self.show_page("instruments")).pack(anchor="w", pady=12)
            return

        catalog = instrument_detail_from_catalog(self.instrument_detail)
        uid = catalog["instrument_uid"]
        # Instrument identity/metadata comes from the already loaded catalog.
        # Market data and trading status remain live API calls.
        fresh = catalog
        try:
            prices = items(self.client.get_last_prices([uid]), "last_prices")
            last_price = decimal(field(prices[0], "price")) if prices else decimal(catalog.get("last_price"))
        except Exception:
            last_price = decimal(catalog.get("last_price"))
        try:
            close = items(self.client.get_close_prices([uid]), "close_prices")
            close_price = decimal(field(close[0], "price")) if close else Decimal("0")
        except Exception:
            close_price = Decimal("0")
        try:
            status = self.client.get_trading_status(uid)
        except Exception:
            status = {}

        title = f"{field(fresh, 'ticker', catalog['ticker'])} — {field(fresh, 'name', catalog['name'])}"
        ttk.Button(self.content, text="← К инструментам", command=lambda: self.show_page("instruments")).pack(anchor="w", pady=(0, 8))
        ttk.Label(self.content, text=title, style="Title.TLabel").pack(anchor="w", pady=(0, 16))

        summary = ttk.Frame(self.content)
        summary.pack(fill="x")
        for col in range(4):
            summary.columnconfigure(col, weight=1)
        _card(self, summary, "Текущая цена", f"{last_price:,.4f} {field(fresh, 'currency', catalog['currency'])}", 0)
        change = last_price - close_price if close_price else Decimal("0")
        change_pct = (change / close_price * Decimal("100")) if close_price else Decimal("0")
        _card(self, summary, "Изменение", f"{change:,.4f} ({change_pct:,.2f}%)", 1)
        _card(self, summary, "Шаг цены", str(field(fresh, "min_price_increment", catalog["min_price_increment"])), 2)
        trading_status = field(status, "trading_status", field(status, "status", ""))
        _card(self, summary, "Торговый статус", str(trading_status or "Неизвестно"), 3)

        details = ttk.Frame(self.content)
        details.pack(fill="x", pady=(18, 10))
        rows = [
            ("Тикер", field(fresh, "ticker", catalog["ticker"])),
            ("UID", uid),
            ("FIGI", field(fresh, "figi", catalog.get("figi", ""))),
            ("Валюта", field(fresh, "currency", catalog["currency"])),
            ("Тип", catalog["instrument_kind"]),
            ("BUY", "Доступна" if field(status, "buy_available_flag", catalog["buy_available"]) else "Недоступна"),
            ("SELL", "Доступна" if field(status, "sell_available_flag", catalog["sell_available"]) else "Недоступна"),
            ("LIMIT", "Доступен" if field(status, "limit_order_available_flag", False) else "Недоступен"),
            ("MARKET", "Доступен" if field(status, "market_order_available_flag", False) else "Недоступен"),
        ]
        for row, (label, value) in enumerate(rows):
            ttk.Label(details, text=f"{label}:", width=16).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Label(details, text=str(value)).grid(row=row, column=1, sticky="w", pady=2)

        position = _find_position(self, uid)
        if position is not None:
            ttk.Label(self.content, text="Позиция", style="Subtitle.TLabel").pack(anchor="w", pady=(14, 4))
            pframe = ttk.Frame(self.content)
            pframe.pack(fill="x")
            for row, (label, value) in enumerate(
                (("Количество", field(position, "balance", 0)),
                 ("Средняя цена", field(position, "average_position_price", field(position, "average_price", ""))),
                 ("P&L", field(position, "expected_yield", field(position, "expected_yield_fifo", ""))))
            ):
                ttk.Label(pframe, text=f"{label}:", width=16).grid(row=row, column=0, sticky="w", pady=2)
                ttk.Label(pframe, text=str(value)).grid(row=row, column=1, sticky="w", pady=2)

        order = ttk.LabelFrame(self.content, text="Быстрая заявка", padding=12)
        order.pack(fill="x", pady=(18, 0))
        side_frame = ttk.Frame(order)
        side_frame.pack(fill="x")
        ttk.Radiobutton(side_frame, text="Купить", variable=self.order_side_v03, value=OrderSide.BUY.value).pack(side="left")
        ttk.Radiobutton(side_frame, text="Продать", variable=self.order_side_v03, value=OrderSide.SELL.value).pack(side="left", padx=12)
        ttk.Label(side_frame, text="Тип:").pack(side="left", padx=(28, 6))
        ttk.Combobox(side_frame, textvariable=self.order_type_v03, state="readonly", values=[x.value for x in (OrderType.MARKET, OrderType.LIMIT, OrderType.BESTPRICE)], width=12).pack(side="left")
        ttk.Label(side_frame, text="Количество:").pack(side="left", padx=(20, 6))
        ttk.Entry(side_frame, textvariable=self.order_quantity_v03, width=10).pack(side="left")
        ttk.Label(side_frame, text="Цена:").pack(side="left", padx=(20, 6))
        ttk.Entry(side_frame, textvariable=self.order_price_v03, width=12).pack(side="left")
        ttk.Button(side_frame, text="Отправить", command=lambda: submit(self)).pack(side="right")

    def submit(self: Any) -> None:
        account_id = self._require_account()
        if not account_id or not self.instrument_detail:
            return
        try:
            quantity = int(self.order_quantity_v03.get())
            order_type = OrderType(self.order_type_v03.get())
            price = Decimal(self.order_price_v03.get()) if self.order_price_v03.get().strip() else None
            request = OrderRequest(
                account_id=account_id,
                instrument_uid=self.instrument_detail["instrument_uid"],
                side=OrderSide(self.order_side_v03.get()),
                order_type=order_type,
                quantity=quantity,
                price=price,
                instrument_kind=self.instrument_detail.get("instrument_kind", "SHARE"),
            )
            validator = TradingValidator(AdapterTradingDataProvider(self.client))
            context = validator.validate(request)
            if not messagebox.askyesno(
                "Подтверждение заявки",
                f"{request.side.value} {request.quantity} лот(ов) {self.instrument_detail['ticker']}\n"
                f"Тип: {request.order_type.value}\n"
                f"Оценочная сумма: {context.estimated_total or Decimal('0')}\n"
                f"Комиссия: {context.estimated_commission or Decimal('0')}",
            ):
                return
            result = OrderService(self.client).create_order(request)
            order_id = field(result, "order_id", "")
            messagebox.showinfo("Заявка отправлена", f"Order ID: {order_id}")
            self.show_page("instrument")
        except Exception as exc:
            messagebox.showerror("Ошибка заявки", str(exc))

    app_class.__init__ = init
    app_class._page_instruments = page_instruments
    app_class._page_instrument = page_instrument
    app_class._instrument_open_detail = open_detail
    app_class._instrument_screen_v03_installed = True


def _card(app: Any, parent: Any, title: str, value: str, column: int) -> None:
    frame = ttk.Frame(parent, style="Card.TFrame", padding=14)
    frame.grid(row=0, column=column, sticky="nsew", padx=5)
    ttk.Label(frame, text=title, style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(frame, text=value, style="CardValue.TLabel").pack(anchor="w", pady=(7, 0))


def _find_position(app: Any, instrument_uid: str) -> Any | None:
    try:
        positions = app.client.get_positions(app.context.require_account_id())
    except Exception:
        return None
    for position in items(positions, "securities", "positions"):
        candidate = str(field(position, "instrument_uid", field(position, "uid", "")))
        if candidate == instrument_uid:
            return position
    return None


from edward.ui.instrument_catalog import INSTRUMENT_KINDS  # noqa: E402
