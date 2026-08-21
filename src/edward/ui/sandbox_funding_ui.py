from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, simpledialog
from typing import Any

from edward.services.balance_service import BalanceService

logger = logging.getLogger("edward.sandbox_funding")


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

    def _money_value(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, dict):
            if "units" in value or "nano" in value:
                return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
            if "value" in value:
                return _money_value(value["value"])
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _parse_payin_balance(value: Any) -> Decimal | None:
        """Accept normal JSON MoneyValue and SDK string fallback returned by adapter."""
        if value is None:
            return None
        if isinstance(value, (dict, Decimal, int, float)):
            return _money_value(value)
        text = str(value)
        match = re.search(r"units=([-+]?\d+(?:\.\d+)?).*?nano=([-+]?\d+)", text)
        if match:
            return Decimal(match.group(1)) + Decimal(match.group(2)) / Decimal("1000000000")
        return None

    def _get_sandbox_rub_balance(self: Any, account_id: str) -> Decimal:
        """Get actual RUB cash from GetSandboxPositions.

        T-Invest returns money positions as MoneyValue-like objects:
        {currency, units, nano}. There is no available/available_value field
        in this response.
        """
        positions = self.client.get_sandbox_positions(account_id)
        money = self._items(positions, "money")
        logger.info("[SANDBOX FUNDING] GetSandboxPositions account_id=%s money=%s", account_id, money)

        for position in money:
            currency = str(self._field(position, "currency", "")).upper()
            if currency != "RUB":
                continue

            # Actual GetSandboxPositions format: currency + units + nano.
            if self._field(position, "units", None) is not None or self._field(position, "nano", None) is not None:
                balance = _money_value(position)
                logger.info("[SANDBOX FUNDING] RUB balance from MoneyValue=%s", balance)
                return balance

            # Keep compatibility with normalized/fallback responses.
            available = self._field(position, "available", None)
            if available is None:
                available = self._field(position, "available_value", None)
            if available is not None:
                balance = _money_value(available)
                logger.info("[SANDBOX FUNDING] RUB balance from available=%s", balance)
                return balance

            raise RuntimeError(
                "В денежной позиции sandbox не найдено поле units/nano либо available/available_value.\n"
                f"Позиция: {position}\n\n"
                f"Ответ GetSandboxPositions: {positions}"
            )

        if not money:
            logger.info("[SANDBOX FUNDING] No money positions yet; treating initial RUB balance as 0")
            return Decimal("0")

        raise RuntimeError(
            "В GetSandboxPositions не найдена денежная позиция RUB.\n"
            f"Money positions: {money}\n\n"
            f"Ответ API: {positions}"
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
            logger.info("[SANDBOX FUNDING] START account_id=%s amount=%s", account_id, amount)
            self.status_var.set("Получение текущего баланса...")
            self.update_idletasks()
            balance_before = _get_sandbox_rub_balance(self, account_id)
            expected_balance = balance_before + amount
            logger.info(
                "[SANDBOX FUNDING] BEFORE account_id=%s balance_before=%s expected=%s",
                account_id,
                balance_before,
                expected_balance,
            )

            self.status_var.set("Пополнение sandbox-счёта...")
            self.update_idletasks()
            result = self.client.sandbox_pay_in(account_id, amount)
            logger.info("[SANDBOX FUNDING] PAYIN RESULT account_id=%s result=%s", account_id, result)

            response_balance_raw = self._field(result, "balance", None)
            if response_balance_raw is None:
                response_balance_raw = self._field(result, "value", None)
            payin_balance = _parse_payin_balance(response_balance_raw)
            if payin_balance is None:
                raise RuntimeError(
                    "SandboxPayIn не вернул распознаваемый фактический баланс.\n"
                    f"Ответ API: {result}"
                )

            self.status_var.set("Проверка фактического баланса после пополнения...")
            self.update_idletasks()
            actual_balance = _get_sandbox_rub_balance(self, account_id)
            logger.info(
                "[SANDBOX FUNDING] AFTER account_id=%s payin_balance=%s actual_balance=%s expected=%s",
                account_id,
                payin_balance,
                actual_balance,
                expected_balance,
            )

            if payin_balance != expected_balance or actual_balance != expected_balance or actual_balance != payin_balance:
                raise RuntimeError(
                    "Баланс после пополнения не совпал с ожидаемым.\n\n"
                    f"Счёт: {account_id}\n"
                    f"Баланс до: {balance_before:,.2f} RUB\n"
                    f"Пополнение: {amount:,.2f} RUB\n"
                    f"Ожидаемый баланс: {expected_balance:,.2f} RUB\n"
                    f"Баланс из SandboxPayIn: {payin_balance:,.2f} RUB\n"
                    f"Фактический баланс GetSandboxPositions: {actual_balance:,.2f} RUB\n"
                    f"Ответ SandboxPayIn: {result}"
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
