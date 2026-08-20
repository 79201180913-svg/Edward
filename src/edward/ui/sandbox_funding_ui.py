from __future__ import annotations

from decimal import Decimal, InvalidOperation
from tkinter import messagebox, simpledialog
from typing import Any

from edward.services.balance_service import BalanceService


def install_sandbox_funding_ui(app_class: type[Any]) -> None:
    """Add sandbox-only account funding controls with expected-vs-real balance validation."""
    if getattr(app_class, "_sandbox_funding_installed", False):
        return

    original_shell = app_class._shell

    def _shell(self: Any) -> None:
        original_shell(self)
        if str(self.environment.value).lower() != "sandbox":
            return
        if getattr(self, "_sandbox_pay_in_button", None) is not None:
            return
        import tkinter as tk
        self._sandbox_pay_in_button = tk.Button(
            self.nav,
            text="Пополнить sandbox-счёт",
            command=self._sandbox_pay_in,
        )
        self._sandbox_pay_in_button.pack(fill="x", pady=2)

    def _get_sandbox_rub_balance(self: Any, account_id: str) -> Decimal:
        """Get the pre-funding RUB cash balance from SandboxPortfolio."""
        portfolio = self.client.get_sandbox_portfolio(account_id)

        # T-Invest SandboxPortfolio exposes cash totals separately from
        # the instrument positions. Prefer total_amount_currencies for cash.
        for field_name in ("total_amount_currencies", "total_amount_portfolio"):
            value = self._field(portfolio, field_name, None)
            if value is not None:
                return BalanceService._decimal(value)

        raise RuntimeError(
            "Не удалось определить текущий RUB-баланс sandbox-счёта.\n"
            f"Ответ GetSandboxPortfolio: {portfolio}"
        )

    def _sandbox_pay_in(self: Any) -> None:
        if str(self.environment.value).lower() != "sandbox":
            messagebox.showwarning("Пополнение", "Пополнение доступно только для sandbox.", parent=self)
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
            amount = Decimal(raw)
        except (InvalidOperation, ValueError):
            messagebox.showerror("Пополнение", "Введите корректную сумму в RUB.", parent=self)
            return

        if not amount.is_finite():
            messagebox.showerror("Пополнение", "Сумма должна быть конечным числом.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror("Пополнение", "Сумма пополнения должна быть больше 0.", parent=self)
            return
        if amount > Decimal("30000000"):
            messagebox.showerror("Пополнение", "Максимальная сумма пополнения — 30 000 000 RUB.", parent=self)
            return

        amount_text = f"{amount:,.2f}".replace(",", " ")
        if not messagebox.askyesno(
            "Подтверждение пополнения",
            f"Пополнить sandbox-счёт:\n{account_id}\n\nСумма: {amount_text} RUB?",
            parent=self,
        ):
            return

        try:
            self.status_var.set("Получение текущего баланса...")
            self.update_idletasks()
            balance_before = _get_sandbox_rub_balance(self, account_id)
            expected_balance = balance_before + amount

            self.status_var.set("Пополнение sandbox-счёта...")
            self.update_idletasks()
            result = self.client.sandbox_pay_in(account_id, amount)

            # SandboxPayIn returns the real current account balance after the
            # operation. This is the authoritative post-operation value.
            response_balance_raw = self._field(result, "balance", None)
            if response_balance_raw is None:
                raise RuntimeError(
                    "SandboxPayIn не вернул фактический баланс.\n"
                    f"Ответ API: {result}"
                )
            actual_balance = BalanceService._decimal(response_balance_raw)

            if actual_balance != expected_balance:
                raise RuntimeError(
                    "Баланс после пополнения не совпал с ожидаемым.\n\n"
                    f"Баланс до: {balance_before:,.2f} RUB\n"
                    f"Пополнение: {amount:,.2f} RUB\n"
                    f"Ожидаемый баланс: {expected_balance:,.2f} RUB\n"
                    f"Фактический баланс из SandboxPayIn: {actual_balance:,.2f} RUB\n"
                    f"Ответ API: {result}"
                )

            self.status_var.set("Sandbox-счёт пополнен и проверен")
            self.refresh_current()
            messagebox.showinfo(
                "Пополнение выполнено",
                f"Счёт успешно пополнен на {amount_text} RUB.\n\n"
                f"Баланс до: {balance_before:,.2f} RUB\n"
                f"Ожидаемый баланс: {expected_balance:,.2f} RUB\n"
                f"Фактический баланс: {actual_balance:,.2f} RUB",
                parent=self,
            )
        except Exception as exc:
            self.status_var.set("Ошибка проверки пополнения sandbox-счёта")
            self._show_error(exc, "пополнение sandbox-счёта")

    app_class._shell = _shell
    app_class._sandbox_pay_in = _sandbox_pay_in
    app_class._get_sandbox_rub_balance = _get_sandbox_rub_balance
    app_class._sandbox_funding_installed = True
