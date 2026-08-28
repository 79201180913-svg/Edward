from __future__ import annotations

from decimal import Decimal
import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.balance_service import BalanceService
from edward.services.currency_service import CurrencyService


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict):
        if "units" in value or "nano" in value:
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        if "value" in value:
            return _decimal(value["value"])
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _items(response: Any, *names: str) -> list[Any]:
    if isinstance(response, list):
        return response
    for name in names:
        value = _field(response, name, None)
        if value is not None:
            return list(value)
    return []


def _money(value: Any, currency: str) -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ") + (f" {currency}" if currency else "")


def open_autonomous_portfolio_window(
    parent: Any,
    client: Any,
    account_id: str,
    display_currency: str = "RUB",
    opportunities: tuple[Any, ...] = (),
) -> tk.Toplevel:
    """Show the current portfolio as a separate autonomous-trading workspace."""
    window = tk.Toplevel(parent)
    window.title("Edward — Портфель автономной торговли")
    window.geometry("1250x700")
    window.minsize(1000, 560)
    window.transient(parent)

    header = ttk.Frame(window, padding=(16, 14))
    header.pack(fill="x")
    ttk.Label(header, text="Портфель", font=("Segoe UI", 18, "bold")).pack(side="left")
    ttk.Label(header, text=f"Счёт: {account_id}").pack(side="left", padx=(16, 0), pady=(6, 0))

    summary_frame = ttk.Frame(window, padding=(16, 0, 16, 12))
    summary_frame.pack(fill="x")
    for column in range(4):
        summary_frame.columnconfigure(column, weight=1)
    summary_values: dict[str, ttk.Label] = {}
    for column, (key, title) in enumerate(
        (("portfolio", "Стоимость портфеля"), ("cash", "Доступно"), ("securities", "В ценных бумагах"), ("positions", "Позиций"))
    ):
        frame = ttk.Frame(summary_frame, relief="solid", borderwidth=1, padding=10)
        frame.grid(row=0, column=column, sticky="nsew", padx=4)
        ttk.Label(frame, text=title).pack(anchor="w")
        value = ttk.Label(frame, text="—", font=("Segoe UI", 14, "bold"))
        value.pack(anchor="w", pady=(6, 0))
        summary_values[key] = value

    controls = ttk.Frame(window, padding=(16, 0, 16, 8))
    controls.pack(fill="x")
    status_var = tk.StringVar(value="Готово")
    ttk.Button(controls, text="Обновить", command=lambda: refresh()).pack(side="left")
    ttk.Label(controls, textvariable=status_var).pack(side="left", padx=12)

    columns = (
        "ticker", "uid", "quantity", "blocked", "price", "value", "pnl", "weight", "decision", "risk", "target", "status"
    )
    tree = ttk.Treeview(window, columns=columns, show="headings", height=18)
    headings = {
        "ticker": "Тикер", "uid": "UID", "quantity": "Количество", "blocked": "Заблокировано",
        "price": "Цена", "value": "Стоимость", "pnl": "P&L", "weight": "Вес %",
        "decision": "Решение", "risk": "Риск", "target": "Цель", "status": "Статус",
    }
    widths = {"ticker": 90, "uid": 250, "quantity": 95, "blocked": 110, "price": 100, "value": 120, "pnl": 100, "weight": 80, "decision": 100, "risk": 80, "target": 100, "status": 150}
    for column in columns:
        tree.heading(column, text=headings[column])
        tree.column(column, width=widths[column], anchor="center")
    tree.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    note = ttk.Label(
        window,
        text="Здесь отображается фактический портфель. Решение Edward берётся из последнего анализа PORTFOLIO, если он уже выполнен.",
        wraplength=1150,
        padding=(16, 0, 16, 12),
    )
    note.pack(fill="x")

    def convert_money(value: Any, source_currency: str) -> str:
        source = str(source_currency or "RUB").upper()
        target = str(display_currency or source).upper()
        try:
            converted = value if source == target else CurrencyService(client).convert(value, source, target)
            return _money(converted, target)
        except Exception:
            return _money(value, source)

    def opportunity_by_uid() -> dict[str, Any]:
        return {str(_field(item, "instrument_uid", "")): item for item in opportunities if _field(item, "instrument_uid", "")}

    def refresh() -> None:
        try:
            balance = BalanceService(client)
            positions_response = balance.get_positions(account_id)
            portfolio_response = balance.get_portfolio(account_id)
            summary = balance.build_summary(positions_response, portfolio_response)
            securities = balance.get_security_positions(positions_response)
            api_positions = _items(portfolio_response, "positions")
            by_uid = {str(_field(item, "instrument_uid", "")): item for item in api_positions}
            decisions = opportunity_by_uid()

            for item in tree.get_children():
                tree.delete(item)

            for position in securities:
                uid = str(_field(position, "instrument_uid", ""))
                portfolio_position = by_uid.get(uid)
                opportunity = decisions.get(uid)
                ticker = str(_field(position, "ticker", _field(portfolio_position, "ticker", "")))
                quantity = _field(position, "balance", _field(position, "quantity", 0))
                blocked = _field(position, "blocked", _field(position, "blocked_lots", 0))
                price = _field(position, "current_price", _field(portfolio_position, "current_price", None))
                value = _field(position, "current_value", _field(position, "value", None))
                if value is None and price is not None:
                    value = _decimal(quantity) * _decimal(price)
                pnl = _field(portfolio_position, "expected_yield", _field(position, "expected_yield", None))
                weight = _field(portfolio_position, "current_weight_pct", None)
                decision = _field(opportunity, "decision", None) or "—"
                risk = _field(opportunity, "risk_score", None)
                target = _field(portfolio_position, "target_weight_pct", None)
                status = _field(opportunity, "status", None) or "CURRENT"
                source_currency = str(_field(position, "currency", summary.currency) or summary.currency).upper()
                tree.insert(
                    "", "end",
                    values=(
                        ticker,
                        uid,
                        quantity,
                        blocked,
                        "—" if price is None else f"{_decimal(price):.4f}",
                        "—" if value is None else convert_money(value, source_currency),
                        "—" if pnl is None else str(pnl),
                        "—" if weight is None else f"{_decimal(weight):.2f}",
                        decision,
                        "—" if risk is None else f"{_decimal(risk):.2f}",
                        "—" if target is None else f"{_decimal(target):.2f}%",
                        status,
                    ),
                )

            summary_values["portfolio"].configure(text=convert_money(summary.portfolio_value, summary.currency))
            summary_values["cash"].configure(text=convert_money(summary.available, summary.currency))
            summary_values["securities"].configure(text=convert_money(summary.securities, summary.currency))
            summary_values["positions"].configure(text=str(len(securities)))
            status_var.set(f"Обновлено: {len(securities)} позиций")
        except Exception as exc:
            status_var.set(f"Ошибка: {type(exc).__name__}: {exc}")

    refresh()
    return window
