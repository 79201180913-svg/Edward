from __future__ import annotations

import re
import traceback
from datetime import datetime
from tkinter import END, Text, filedialog, messagebox, ttk
import tkinter as tk
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(token\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(authorization\s*[=:]\s*)(?:bearer\s+)?[^\s,;]+"),
)


def sanitize_log(text: str) -> str:
    """Remove common credential formats before displaying/copying diagnostics."""
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(lambda m: f"{m.group(1)}***MASKED***", result)
    return result


def build_error_log(exc: BaseException, context: str = "GUI") -> str:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return sanitize_log(
        "Edward Trading Platform v0.1\n"
        f"Time: {timestamp}\n"
        f"Context: {context}\n"
        f"Error: {type(exc).__name__}: {exc}\n"
        "\nTraceback:\n"
        f"{details}"
    )


def show_error_dialog(parent: tk.Misc, exc: BaseException, context: str = "GUI") -> str:
    """Show detailed diagnostics with one-click copy and optional save."""
    log_text = build_error_log(exc, context)

    dialog = tk.Toplevel(parent)
    dialog.title("Ошибка Edward")
    dialog.geometry("900x600")
    dialog.minsize(700, 450)
    dialog.transient(parent)
    dialog.grab_set()

    outer = ttk.Frame(dialog, padding=16)
    outer.pack(fill="both", expand=True)

    ttk.Label(
        outer,
        text="Произошла ошибка",
        font=("Segoe UI", 16, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        outer,
        text="Скопируйте диагностический лог и отправьте его для анализа. Секретные данные автоматически маскируются.",
        wraplength=820,
    ).pack(anchor="w", pady=(6, 12))

    frame = ttk.Frame(outer)
    frame.pack(fill="both", expand=True)
    text = Text(frame, wrap="none", font=("Consolas", 10), undo=False)
    text.insert("1.0", log_text)
    text.configure(state="disabled")
    text.pack(side="left", fill="both", expand=True)

    y_scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    y_scroll.pack(side="right", fill="y")
    x_scroll = ttk.Scrollbar(outer, orient="horizontal", command=text.xview)
    x_scroll.pack(fill="x")
    text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x", pady=(12, 0))

    def copy_log() -> None:
        dialog.clipboard_clear()
        dialog.clipboard_append(log_text)
        dialog.update()
        messagebox.showinfo("Edward", "Лог скопирован в буфер обмена.", parent=dialog)

    def save_log() -> None:
        path = filedialog.asksaveasfilename(
            parent=dialog,
            title="Сохранить диагностический лог",
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
            initialfile="edward_error.log.txt",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(log_text)
            messagebox.showinfo("Edward", f"Лог сохранён:\n{path}", parent=dialog)
        except OSError as save_exc:
            messagebox.showerror("Edward", f"Не удалось сохранить лог:\n{save_exc}", parent=dialog)

    ttk.Button(buttons, text="Копировать лог", command=copy_log).pack(side="left")
    ttk.Button(buttons, text="Сохранить лог", command=save_log).pack(side="left", padx=8)
    ttk.Button(buttons, text="Закрыть", command=dialog.destroy).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.wait_window()
    return log_text


def install_error_reporting(app_class: type[Any]) -> None:
    """Install detailed error handling in the existing GUI presentation class."""
    original_show_error = app_class._show_error
    original_report_callback_exception = getattr(app_class, "report_callback_exception", None)

    def _show_error(self: Any, exc: Exception) -> None:
        self.status_var.set("Ошибка")
        show_error_dialog(self, exc, self.current_page)

    def report_callback_exception(self: Any, exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:
        exc = exc_value
        if exc is None:
            exc = RuntimeError("Неизвестная ошибка Tkinter callback")
        show_error_dialog(self, exc, "Tkinter callback")
        if original_report_callback_exception is not None:
            # Keep Tkinter's standard reporting behavior available without
            # replacing the user-facing diagnostic dialog.
            try:
                original_report_callback_exception(self, exc_type, exc_value, exc_tb)
            except Exception:
                pass

    app_class._show_error = _show_error
    app_class.report_callback_exception = report_callback_exception
