from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, simpledialog
from typing import Any

from edward.services.balance_service import BalanceService


def install_sandbox_funding_ui(app_class: type[Any]) -> None:
    """Add sandbox-only account funding controls with post-funding balance validation."""
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

    def _get_sandbox_rub_balance(self, account_id: str) -> Decimal:
        positions = self.client.get_positions(account_id)
        money = BalanceService.get_money_positions(positions)
        rub = Decimal("0")
        for position in money:
            currency = str(self._field(position, "currency", "")).upper()
            if currency != "RUB":
                continue
            rub += BalanceService._decimal(self._field(position, "available"))
        return rub

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
            balance_before = self._get_sandbox_rub_balance(account_id)
            expected_balance = balance_before + amount

            self.status_var.set("Пополнение sandbox-счёта...")
            self.update_idletasks()
            result = self.client.sandbox_pay_in(account_id, amount)

            # SandboxPayInResponse contains the current balance, but we also
            # verify it independently through GetPositions to avoid false success.
            response_balance = self._field(result, "balance", None)
            if response_balance is not None:
                response_balance = BalanceService._decimal(response_balance)

            actual_balance = None
            last_error: Exception | None = None
            for _ in range(6):
                try:
                    actual_balance = self._get_sandbox_rub_balance(account_id)
                    if actual_balance == expected_balance:
                        break
                except Exception as exc:
                    last_error = exc
                time.sleep(0.5)

            if actual_balance is None:
                raise RuntimeError(
                    f"Не удалось получить баланс после пополнения.\n"
                    f"Баланс до: {balance_before} RUB\n"
                    f"Ожидалось: {expected_balance} RUB\n"
                    f"Ответ SandboxPayIn: {result}\n"
                    f"Ошибка получения баланса: {last_error}"
                )

            if actual_balance != expected_balance:
                raise RuntimeError(
                    "Баланс после пополнения не совпал с ожидаемым.\n\n"
                    f"Баланс до: {balance_before:,.2f} RUB\n"
                    f"Пополнение: {amount:,.2f} RUB\n"
                    f"Ожидаемый баланс: {expected_balance:,.2f} RUB\n"
                    f"Фактический баланс: {actual_balance:,.2f} RUB\n"
                    f"Баланс из SandboxPayIn: {response_balance if response_balance is not None else 'не передан'}\n"
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
    app_class._sandbox_funding_installed = True
