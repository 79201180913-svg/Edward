from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from edward.security.token_store import TokenStore


def request_and_save_token(store: TokenStore) -> str | None:
    """Show a Windows-friendly token dialog and save the token securely."""
    result: dict[str, str | None] = {"token": None}

    root = tk.Tk()
    root.title("Edward Trading Platform")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = tk.Frame(root, padx=24, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="T-Invest API Token",
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w")

    tk.Label(
        frame,
        text="Введите токен T-Invest. Он будет сохранён локально\nв защищённом хранилище Windows.",
        justify="left",
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(8, 12))

    token_var = tk.StringVar()
    entry = tk.Entry(
        frame,
        textvariable=token_var,
        width=58,
        show="•",
        font=("Segoe UI", 10),
        relief="solid",
        bd=1,
    )
    entry.pack(fill="x")
    entry.focus_force()

    # Use Tk's native virtual clipboard events. Unlike manual Control-V
    # bindings, these are handled by the standard Entry widget clipboard
    # implementation on Windows.
    def paste(_event=None):
        try:
            entry.event_generate("<<Paste>>")
        except tk.TclError:
            pass
        return "break"

    def copy(_event=None):
        try:
            entry.event_generate("<<Copy>>")
        except tk.TclError:
            pass
        return "break"

    def cut(_event=None):
        try:
            entry.event_generate("<<Cut>>")
        except tk.TclError:
            pass
        return "break"

    def select_all(_event=None):
        entry.select_range(0, "end")
        entry.icursor("end")
        return "break"

    entry.bind("<Control-v>", paste)
    entry.bind("<Control-V>", paste)
    entry.bind("<Control-c>", copy)
    entry.bind("<Control-C>", copy)
    entry.bind("<Control-x>", cut)
    entry.bind("<Control-X>", cut)
    entry.bind("<Control-a>", select_all)
    entry.bind("<Control-A>", select_all)
    entry.bind("<Shift-Insert>", paste)

    def cancel() -> None:
        result["token"] = None
        root.destroy()

    def save() -> None:
        token = token_var.get().strip()
        if not token:
            messagebox.showwarning(
                "Edward Trading Platform",
                "Токен не может быть пустым.",
                parent=root,
            )
            entry.focus_force()
            return

        try:
            store.save(token)
        except Exception as exc:
            messagebox.showerror(
                "Edward Trading Platform",
                f"Не удалось сохранить токен:\n{exc}",
                parent=root,
            )
            return

        result["token"] = token
        root.destroy()

    buttons = tk.Frame(frame)
    buttons.pack(fill="x", pady=(16, 0))

    tk.Button(
        buttons,
        text="Сохранить и продолжить",
        command=save,
        width=23,
        default="active",
    ).pack(side="right")
    tk.Button(
        buttons,
        text="Отмена",
        command=cancel,
        width=12,
    ).pack(side="right", padx=(0, 8))

    root.bind("<Return>", lambda _event: save())
    root.bind("<Escape>", lambda _event: cancel())
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()

    return result["token"]
