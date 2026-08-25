from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.instrument_decision_context_service import InstrumentDecisionContextService
from edward.services.market_decision_context_service import MarketDecisionContextService


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _quotation_to_text(value: Any) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, str):
        return value
    units = _field(value, "units")
    nano = _field(value, "nano")
    if units is not None or nano is not None:
        try:
            return f"{float(units or 0) + float(nano or 0) / 1_000_000_000:.4f}"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def install_decision_context_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_decision_context_ui_v04_installed", False):
        return

    original_page = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        original_page(self)
        detail = getattr(self, "instrument_detail", None)
        if not detail or getattr(self, "decision_context_frame", None) is not None:
            return

        frame = ttk.LabelFrame(self.content, text="Decision Engine 0.4 — текущий контекст", padding=10)
        frame.pack(fill="x", pady=(10, 0))
        self.decision_context_frame = frame

        vars_map = {
            "uid": tk.StringVar(value="—"),
            "price": tk.StringVar(value="—"),
            "status": tk.StringVar(value="—"),
            "buy": tk.StringVar(value="—"),
            "sell": tk.StringVar(value="—"),
            "available": tk.StringVar(value="—"),
        }
        self.decision_context_vars = vars_map

        rows = (
            ("UID", "uid"),
            ("Текущая цена", "price"),
            ("Trading Status", "status"),
            ("BUY доступен", "buy"),
            ("SELL доступен", "sell"),
            ("Инструмент доступен", "available"),
        )
        for index, (label, key) in enumerate(rows):
            ttk.Label(frame, text=f"{label}:").grid(row=index // 3, column=(index % 3) * 2, sticky="w", padx=(0, 5), pady=2)
            ttk.Label(frame, textvariable=vars_map[key]).grid(row=index // 3, column=(index % 3) * 2 + 1, sticky="w", padx=(0, 18), pady=2)

        ttk.Button(frame, text="Обновить контекст", command=lambda: _refresh_context(self)).grid(row=2, column=4, columnspan=2, sticky="e", padx=(10, 0))
        _refresh_context(self)

    app_class._page_instrument = page_instrument
    app_class._decision_context_ui_v04_installed = True


def _refresh_context(app: Any) -> None:
    detail = getattr(app, "instrument_detail", None)
    variables = getattr(app, "decision_context_vars", None)
    if not detail or not variables:
        return

    uid = str(detail.get("instrument_uid") or detail.get("uid") or "")
    variables["uid"].set(uid or "—")
    if not uid:
        variables["available"].set("Нет UID")
        return

    try:
        status = app.client.get_trading_status(uid)
        instrument_context = InstrumentDecisionContextService().build(detail, status)
        variables["status"].set(instrument_context.trading_status or "—")
        variables["buy"].set("ДА" if instrument_context.buy_available else "НЕТ")
        variables["sell"].set("ДА" if instrument_context.sell_available else "НЕТ")
        variables["available"].set("ДА" if instrument_context.available else "НЕТ")

        prices = app.client.get_last_prices([uid])
        items = prices if isinstance(prices, list) else _field(prices, "last_prices", []) or []
        price_item = next((item for item in items if str(_field(item, "instrument_uid", _field(item, "uid", ""))) == uid), None)
        market_context = MarketDecisionContextService().build(last_price=_field(price_item, "price") if price_item is not None else None)
        variables["price"].set(f"{market_context.current_price:.4f}" if market_context.current_price is not None else "—")
    except Exception as exc:
        variables["status"].set(f"Ошибка: {exc}")
        variables["available"].set("—")
