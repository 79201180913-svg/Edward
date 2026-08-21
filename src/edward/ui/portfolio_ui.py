from __future__ import annotations

from decimal import Decimal

from edward.services.balance_service import BalanceService


def install_portfolio_ui() -> None:
    """Extend the portfolio page with cash positions and portfolio total."""
    from edward.ui.app import EdwardApp

    original_page_portfolio = EdwardApp._page_portfolio

    def _page_portfolio(self):
        import tkinter as tk
        from tkinter import ttk

        ttk.Label(self.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        aid = self._require_account()
        if not aid:
            return

        positions = self.client.get_positions(aid)
        portfolio = self.client.get_portfolio(aid)
        summary = BalanceService.build_summary(positions, portfolio)
        currency = summary.currency or "RUB"

        summary_frame = ttk.Frame(self.content)
        summary_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            summary_frame,
            text=f"Доступно: {self._money(summary.available, currency)} | "
                 f"Стоимость портфеля: {self._money(summary.portfolio_value, currency)} | "
                 f"Ценные бумаги: {self._money(summary.securities, currency)}",
        ).pack(anchor="w")

        tree = self._tree(
            self.content,
            ("Тип", "Тикер", "UID", "Количество", "Заблокировано", "Цена", "Стоимость", "Доходность"),
            (110, 110, 330, 120, 140, 120, 140, 130),
        )

        money_rows = self._items(positions, "money")
        for money in money_rows:
            cur = str(self._field(money, "currency", currency)).upper()
            available = BalanceService._decimal(
                BalanceService._money_field(money, "available", "available_value")
            )
            blocked = BalanceService._decimal(
                BalanceService._money_field(money, "blocked", "blocked_value")
            )
            tree.insert(
                "",
                "end",
                values=(
                    "Денежные средства",
                    cur,
                    "CASH",
                    self._money(available, cur),
                    self._money(blocked, cur),
                    self._money(Decimal("1"), cur),
                    self._money(available, cur),
                    "—",
                ),
            )

        securities_rows = self._items(positions, "securities")
        for position in securities_rows:
            quantity = self._decimal(self._field(position, "quantity", self._field(position, "balance", 0)))
            price = self._decimal(self._field(position, "current_price", self._field(position, "price", 0)))
            explicit_value = self._field(position, "value", None)
            value = self._decimal(explicit_value) if explicit_value is not None else price * quantity
            tree.insert(
                "",
                "end",
                values=(
                    "Ценная бумага",
                    self._field(position, "ticker", ""),
                    self._field(position, "instrument_uid", self._field(position, "figi", "")),
                    self._money(quantity),
                    self._money(self._field(position, "blocked_lots", self._field(position, "blocked", 0))),
                    self._money(price),
                    self._money(value, currency),
                    self._money(self._field(position, "expected_yield", self._field(position, "expected_yield_fifo", 0)), currency),
                ),
            )

        if not money_rows and not securities_rows:
            ttk.Label(self.content, text="Позиции портфеля отсутствуют.").pack(anchor="w", pady=10)

    EdwardApp._page_portfolio = _page_portfolio
