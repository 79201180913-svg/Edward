from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Type

from edward.services.execution_opportunity_registry_v06 import GLOBAL_EXECUTION_OPPORTUNITY_REGISTRY
from edward.services.execution_queue_action_v06 import enqueue_button_text


def install_execution_opportunity_action_ui(app_class: Type[Any]) -> None:
    if getattr(app_class, "_execution_opportunity_action_ui_v06_installed", False):
        return
    original_page = app_class._page_opportunities

    def wrapped_page(self: Any) -> None:
        original_page(self)
        tree = _find_tree(self.content)
        if tree is None or getattr(tree, "_execution_action_installed", False):
            return

        action_frame = ttk.Frame(self.content)
        action_frame.pack(fill="x", pady=(8, 0))
        selected_var = tk.StringVar(value="Выберите готовый инструмент для передачи в исполнение.")
        ttk.Label(action_frame, textvariable=selected_var).pack(side="left")
        action_button = ttk.Button(action_frame, text="Исполнение недоступно", state="disabled")
        action_button.pack(side="right")

        def current_result() -> Any | None:
            selection = tree.selection()
            if not selection:
                return None
            values = tree.item(selection[0]).get("values", ())
            if not values:
                return None
            return GLOBAL_EXECUTION_OPPORTUNITY_REGISTRY.get(str(values[0]))

        def refresh_action(_event: Any = None) -> None:
            result = current_result()
            text = enqueue_button_text(result)
            action_button.configure(text=text, state="normal" if text == "Передать в исполнение" else "disabled")
            if result is None:
                selected_var.set("Выберите готовый инструмент для передачи в исполнение.")
            elif text == "Передать в исполнение":
                selected_var.set(f"{getattr(result, 'ticker', '—')} готов к передаче в исполнение")
            else:
                selected_var.set(f"{getattr(result, 'ticker', '—')}: исполнение недоступно")

        def enqueue_selected() -> None:
            result = current_result()
            if result is None:
                return
            action = getattr(self, "_execution_queue_action_controller", None)
            if action is None:
                messagebox.showwarning("Центр исполнения", "Сервис исполнения ещё не подключён.")
                return
            try:
                accepted = action.enqueue(result)
                if accepted.accepted:
                    center = getattr(self, "_execution_center_controller", None)
                    if center is not None and accepted.request is not None:
                        bridge = getattr(self, "_execution_bridge", None)
                        if bridge is not None:
                            bridge_item = bridge.get(accepted.request.execution_id)
                            if bridge_item is not None and hasattr(center, "load_queue_item"):
                                center.load_queue_item(bridge_item)
                    messagebox.showinfo("Центр исполнения", "Решение передано в очередь исполнения. Заявка не отправлена.")
                    if hasattr(self, "_open_execution_center"):
                        self._open_execution_center()
                else:
                    messagebox.showwarning("Центр исполнения", accepted.reason or "Решение заблокировано и не добавлено в очередь.")
            except Exception as exc:
                messagebox.showerror("Центр исполнения", str(exc))
            refresh_action()

        tree.bind("<<TreeviewSelect>>", refresh_action, add="+")
        action_button.configure(command=enqueue_selected)
        tree._execution_action_installed = True
        refresh_action()

    app_class._page_opportunities = wrapped_page
    app_class._execution_opportunity_action_ui_v06_installed = True


def _find_tree(widget: Any) -> Any | None:
    for child in widget.winfo_children():
        if isinstance(child, ttk.Treeview):
            return child
        nested = _find_tree(child)
        if nested is not None:
            return nested
    return None


__all__ = ["install_execution_opportunity_action_ui"]
