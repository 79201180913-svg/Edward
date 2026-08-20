from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Any


def install_sandbox_funding_ui(app_class: type[Any]) -> None:
    """Add sandbox-only account funding controls to the existing GUI shell."""
    original_shell = app_class._shell

    def _shell(self: Any) -> None:
        original_shell(self)
        if str(self.environment.value).lower() != "sandbox":
            return
        tk.Button(
            self.nav,
            text="Пополнить sandbox-счёт",
            command=self._sandbox_pay_in,
        ).pack(fill="x", pady=2)

    def _sandbox_pay_in(self: Any) -> None:
        if str(self.environment.value).lower() != "sandbox":
            return
        account_id = self._require_account()
        if not account_id:
            return
        raw = simpledialog.askstring(
            "Пополнение sandbox-счёта",
            "Сумма пополнения в RUB:\n\nДопустимо: больше 0, максимум 30 000 000 RUB.",
            parent=self,
        )
        if raw is None:
            return
        raw = raw.strip().replace(" ", "").replace(",", ".")
        try:
            amount = float(raw)
        except ValueError:
            messagebox.showerror("Пополнение", "Введите корректную сумму в RUB.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror("Пополнение", "Сумма пополнения должна быть больше 0.", parent=self)
            return
        if amount > 30_000_000:
            messagebox.showerror("Пополнение", "Максимальная сумма пополнения — 30 000 000 RUB.", parent=self)
            return
        try:
            result = self.client.sandbox_pay_in(account_id, raw)
            balance = self._field(result, "balance", None)
            self._refresh_accounts()
            self.refresh_current()
            if balance is not None:
                messagebox.showinfo(
                    "Пополнение",
                    f"Счёт успешно пополнен на {amount:,.2f} RUB.\n\nТекущий баланс: {balance}",
                    parent=self,
                )
            else:
                messagebox.showinfo("Пополнение", f"Счёт успешно пополнен на {amount:,.2f} RUB.", parent=self)
        except Exception as exc:
            self._show_error(exc, "пополнение sandbox-счёта")

    app_class._shell = _shell
    app_class._sandbox_pay_in = _sandbox_pay_in
