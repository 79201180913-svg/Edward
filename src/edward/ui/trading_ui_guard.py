from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import ttk


def install_trading_ui_guard(app_class: type[Any]) -> None:
    """Prevent selection/submission of unavailable buy/sell operations in the GUI."""
    original_page_order = app_class._page_order

    def _page_order(self: Any) -> None:
        original_page_order(self)

        instrument = self.selected_instrument or {}
        buy_available = bool(instrument.get("buy_available", False))
        sell_available = bool(instrument.get("sell_available", False))

        operation_combo: ttk.Combobox | None = None
        submit_button: ttk.Button | None = None

        def walk(widget: tk.Misc) -> None:
            nonlocal operation_combo, submit_button
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox) and operation_combo is None:
                    # The first combobox on the order page is the operation field.
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
            allowed = selected == "Покупка" and buy_available or selected == "Продажа" and sell_available
            submit_button.configure(state="normal" if allowed else "disabled")
            if selected == "Покупка" and not buy_available:
                self.status_var.set("Покупка недоступна для выбранного инструмента")
            elif selected == "Продажа" and not sell_available:
                self.status_var.set("Продажа недоступна для выбранного инструмента")

        operation_combo.bind("<<ComboboxSelected>>", refresh_submit_state, add="+")
        refresh_submit_state()

    app_class._page_order = _page_order
