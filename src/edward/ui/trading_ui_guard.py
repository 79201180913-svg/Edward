from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import ttk


def install_trading_ui_guard(app_class: type[Any]) -> None:
    """Prevent selection/submission of unavailable buy/sell operations in the GUI."""
    original_page_order = app_class._page_order

    def _show_trading_unavailable(self: Any, error: Exception | None = None) -> None:
        for child in self.content.winfo_children():
            child.destroy()

        instrument = self.selected_instrument or {}
        ticker = str(instrument.get("ticker", ""))

        ttk.Label(
            self.content,
            text="Торговля недоступна",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            self.content,
            text=(
                f"Инструмент: {ticker}\n"
                "Для выбранного инструмента сейчас нет доступных типов торговых заявок."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        if error is not None:
            ttk.Label(
                self.content,
                text=str(error),
                justify="left",
                wraplength=900,
            ).pack(anchor="w", pady=(0, 12))

        submit_button = ttk.Button(
            self.content,
            text="Проверить и подтвердить",
            state="disabled",
        )
        submit_button.pack(anchor="w")
        self.status_var.set("Торговля недоступна для выбранного инструмента")

    def _page_order(self: Any) -> None:
        try:
            original_page_order(self)
        except ValueError as exc:
            message = str(exc)
            if "нет доступных типов заявок" in message:
                _show_trading_unavailable(self, exc)
                return
            raise

        instrument = self.selected_instrument or {}
        buy_available = bool(instrument.get("buy_available", False))
        sell_available = bool(instrument.get("sell_available", False))

        operation_combo: ttk.Combobox | None = None
        submit_button: ttk.Button | None = None

        def walk(widget: tk.Misc) -> None:
            nonlocal operation_combo, submit_button
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox) and operation_combo is None:
                    operation_combo = child
                elif isinstance(child, ttk.Button) and child.cget("text") == "Проверить и подтвердить":
                    submit_button = child
                walk(child)

        walk(self.content)

        if operation_combo is None or submit_button is None:
            return

        operations: list[str] = []
        if buy_available:
            operations.append("Покупка")
        if sell_available:
            operations.append("Продажа")

        operation_combo.configure(values=operations)

        if not operations:
            operation_combo.configure(state="disabled")
            submit_button.configure(state="disabled")
            self.status_var.set("Покупка и продажа недоступны для выбранного инструмента")
            return

        current = operation_combo.get()
        if current not in operations:
            operation_combo.set(operations[0])

        def refresh_submit_state(*_args: Any) -> None:
            selected = operation_combo.get()
            allowed = (
                (selected == "Покупка" and buy_available)
                or (selected == "Продажа" and sell_available)
            )
            submit_button.configure(state="normal" if allowed else "disabled")
            if selected == "Покупка" and not buy_available:
                self.status_var.set("Покупка недоступна для выбранного инструмента")
            elif selected == "Продажа" and not sell_available:
                self.status_var.set("Продажа недоступна для выбранного инструмента")

        operation_combo.bind("<<ComboboxSelected>>", refresh_submit_state, add="+")
        refresh_submit_state()

    app_class._page_order = _page_order
