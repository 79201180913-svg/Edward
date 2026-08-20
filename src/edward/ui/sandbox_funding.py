from __future__ import annotations

from decimal import Decimal, InvalidOperation
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from edward.config.settings import Environment


def install_sandbox_funding(app_class: type[Any]) -> None:
    """Add a sandbox-only account funding action to the GUI."""
    if getattr(app_class, "_sandbox_funding_installed", False):
        return

    original_shell = app_class._shell

    def _pay_in(self: Any) -> None:
        if self.environment is not Environment.SANDBOX:
            return
        account_id = self._require_account()
        if not account_id:
            return

        value = simpledialog.askstring(
            "Пополнение sandbox-счёта",
            "Введите сумму пополнения в RUB:\n\nДопустимый диапазон: 0 < сумма ≤ 30 000 000",
            parent=self,
        )
        if value is None:
            return

        value = value.strip().replace(" ", "").replace(",", ".")
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError):
            messagebox.showerror("Пополнение", "Введите корректную сумму.", parent=self)
            return

        if amount <= 0:
            messagebox.showerror("Пополнение", "Сумма должна быть больше 0.", parent=self)
            return
        if amount > Decimal("30000000"):
            messagebox.showerror("Пополнение", "Максимальная сумма пополнения — 30 000 000 RUB.", parent=self)
            return

        if not messagebox.askyesno(
            "Подтверждение пополнения",
            f"Пополнить sandbox-счёт на {amount:,.2f} RUB?".replace(",", " "),
            parent=self,
        ):
            return

        try:
            result = self.client.sandbox_pay_in(account_id, amount)
            balance = self._field(result, "balance", None)
            self._refresh_accounts()
            self._clear()
            self._show_page(self.current_page)
            if balance is not None:
                messagebox.showinfo(
                    "Пополнение выполнено",
                    f"Счёт пополнен.\nНовый баланс: {self._money(balance, 'RUB')}",
                    parent=self,
                )
            else:
                messagebox.showinfo("Пополнение выполнено", "Sandbox-счёт успешно пополнен.", parent=self)
        except Exception as exc:
            self._show_error(exc, "пополнение sandbox-счёта")

    def _shell(self: Any) -> None:
        original_shell(self)
        if self.environment is not Environment.SANDBOX:
            return
        if getattr(self, "_sandbox_funding_button", None) is not None:
            return
        self._sandbox_funding_button = ttk.Button(
            self.nav,
            text="Пополнить sandbox-счёт",
            command=self._pay_in,
        )
        self._sandbox_funding_button.pack(fill="x", pady=2)

    app_class._pay_in = _pay_in
    app_class._shell = _shell
    app_class._sandbox_funding_installed = True
