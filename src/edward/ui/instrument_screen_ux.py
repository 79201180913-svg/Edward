from __future__ import annotations

from decimal import Decimal
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

from edward.services.order_service import OrderType


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


def _pretty_step(value: Any, currency: str) -> str:
    amount = _decimal(value)
    text = format(amount, "f").rstrip("0").rstrip(".") or "0"
    return f"{text} {currency.upper()}"


def _status_text(value: Any) -> str:
    mapping = {
        "SECURITY_TRADING_STATUS_NORMAL_TRADING": "Торги идут",
        "SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING": "Торги недоступны",
        "SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING_FOR_SESSION": "Торги недоступны на текущую сессию",
    }
    return mapping.get(str(value), str(value) if value else "Неизвестно")


def _walk(widget: Any):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _find_labeled_value(container: Any, prefix: str) -> tuple[Any, Any] | None:
    labels = [w for w in _walk(container) if isinstance(w, ttk.Label)]
    for label in labels:
        try:
            text = str(label.cget("text"))
        except Exception:
            continue
        if text.startswith(prefix):
            parent = label.master
            siblings = [w for w in parent.winfo_children() if isinstance(w, ttk.Label)]
            if len(siblings) >= 2:
                return label, siblings[-1]
    return None


def install_instrument_screen_ux(app_class: type[Any]) -> None:
    if getattr(app_class, "_instrument_screen_ux_installed", False):
        return

    original = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        original(self)
        detail = getattr(self, "instrument_detail", None)
        if not detail:
            return

        uid = str(detail.get("instrument_uid", ""))
        try:
            status = self.client.get_trading_status(uid)
        except Exception:
            status = {}
        try:
            prices = self.client.get_last_prices([uid])
            rows = prices.get("last_prices", []) if isinstance(prices, dict) else []
            current_price = _decimal(_field(rows[0], "price")) if rows else Decimal("0")
        except Exception:
            current_price = Decimal("0")

        currency = str(detail.get("currency", "RUB"))
        limit_available = bool(_field(status, "limit_order_available_flag", False))
        market_available = bool(_field(status, "market_order_available_flag", False))
        bestprice_available = bool(_field(status, "bestprice_order_available_flag", False))
        trading_status = _status_text(_field(status, "trading_status", _field(status, "status", "")))

        # Translate technical status text and price-step rendering.
        for widget in _walk(self.content):
            if not isinstance(widget, ttk.Label):
                continue
            try:
                text = str(widget.cget("text"))
            except Exception:
                continue
            if text.startswith("SECURITY_TRADING_STATUS_"):
                widget.configure(text=trading_status)
            elif text.startswith("{'units':") or text.startswith('{"units":'):
                widget.configure(text=_pretty_step(text, currency))

        # Hide FIGI completely; it is an internal identifier, not a trader-facing field.
        figi = _find_labeled_value(self.content, "FIGI:")
        if figi:
            figi[0].grid_remove()
            figi[1].grid_remove()

        # Find the quick-order controls and enforce current trading-status capabilities.
        comboboxes = [w for w in _walk(self.content) if isinstance(w, ttk.Combobox)]
        if comboboxes:
            order_type = comboboxes[-1]
            values = []
            if limit_available:
                values.append(OrderType.LIMIT.value)
            if market_available:
                values.append(OrderType.MARKET.value)
            if bestprice_available:
                values.append(OrderType.BESTPRICE.value)
            order_type.configure(values=values)

            current = str(order_type.get())
            if current not in values:
                if values:
                    order_type.set(values[0])
                else:
                    order_type.set("")
                order_type.configure(state="disabled")
            else:
                order_type.configure(state="readonly")

            def on_type_change(_event: Any = None) -> None:
                selected = str(order_type.get())
                entries = [w for w in _walk(self.content) if isinstance(w, ttk.Entry)]
                price_entry = entries[-1] if entries else None
                if price_entry is None:
                    return
                if selected == OrderType.LIMIT.value:
                    price_entry.configure(state="normal")
                    if current_price > 0:
                        price_entry.delete(0, tk.END)
                        price_entry.insert(0, format(current_price, "f"))
                else:
                    price_entry.delete(0, tk.END)
                    price_entry.configure(state="disabled")

            order_type.bind("<<ComboboxSelected>>", on_type_change, add="+")
            on_type_change()

            if not values:
                messagebox.showwarning(
                    "Заявка",
                    "Для выбранного инструмента сейчас недоступны MARKET, LIMIT и BESTPRICE.",
                    parent=self,
                )

    app_class._page_instrument = page_instrument
    app_class._instrument_screen_ux_installed = True
