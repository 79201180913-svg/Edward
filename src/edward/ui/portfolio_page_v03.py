from __future__ import annotations

from decimal import Decimal
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

from edward.services.balance_service import BalanceService


def field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def items(response: Any, *names: str) -> list[Any]:
    if isinstance(response, list):
        return response
    for name in names:
        value = field(response, name, None)
        if value is not None:
            return list(value or [])
    return []


def position_metrics(position: Any) -> dict[str, Decimal | None]:
    quantity = decimal(field(position, "balance", field(position, "quantity", 0)))
    current_price = decimal(field(position, "current_price", field(position, "currentPrice", 0)))
    average_price_raw = field(position, "average_position_price", field(position, "average_price", None))
    average_price = decimal(average_price_raw) if average_price_raw not in (None, "") else None
    expected_yield_raw = field(position, "expected_yield", field(position, "expected_yield_fifo", None))
    expected_yield = decimal(expected_yield_raw) if expected_yield_raw not in (None, "") else None

    market_value = quantity * current_price
    pnl = expected_yield

    if average_price is None and pnl is not None:
        invested_value = market_value - pnl
        if quantity != 0:
            average_price = invested_value / quantity

    if pnl is None and average_price is not None:
        pnl = (current_price - average_price) * quantity

    cost_value = average_price * quantity if average_price is not None else None
    pnl_pct = (pnl / cost_value * Decimal("100")) if pnl is not None and cost_value not in (None, Decimal("0")) else None

    return {
        "quantity": quantity,
        "current_price": current_price,
        "average_price": average_price,
        "market_value": market_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }


def format_money(value: Decimal | None, currency: str) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ") + f" {currency}"


def format_number(value: Decimal | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _last_price_map(app: Any, positions: list[Any]) -> dict[str, Decimal]:
    ids: list[str] = []
    for position in positions:
        uid = str(field(position, "instrument_uid", field(position, "uid", "")) or "")
        if uid and uid not in ids:
            ids.append(uid)
    if not ids:
        return {}

    try:
        response = app.client.get_last_prices(ids)
    except Exception:
        return {}

    result: dict[str, Decimal] = {}
    for item in items(response, "last_prices", "prices"):
        uid = str(field(item, "instrument_uid", field(item, "instrument_id", field(item, "uid", ""))) or "")
        price = field(item, "price", field(item, "last_price", None))
        if uid and price is not None:
            result[uid] = decimal(price)
    return result


def install_portfolio_page(app_class: type[Any]) -> None:
    """Install the production portfolio page without adding a UI overlay."""
    if getattr(app_class, "_portfolio_page_v03_installed", False):
        return

    def open_instrument(self: Any, position: Any, side: str | None = None) -> None:
        uid = str(field(position, "instrument_uid", field(position, "uid", "")) or "")
        if not uid:
            messagebox.showwarning("Инструмент", "Для позиции не найден UID инструмента.")
            return

        ticker = str(field(position, "ticker", "") or "")
        currency = str(field(position, "currency", "RUB") or "RUB").upper()
        current_price = field(position, "current_price", "")

        self.instrument_detail = {
            "ticker": ticker,
            "name": ticker,
            "currency": currency,
            "last_price": current_price,
            "min_price_increment": field(position, "min_price_increment", ""),
            "buy_available": True,
            "sell_available": True,
            "api_trade_available": True,
            "uid": uid,
            "instrument_uid": uid,
            "instrument_kind": "SHARE",
        }
        if side is not None and hasattr(self, "order_side_v03"):
            self.order_side_v03.set(side)
        self.show_page("instrument")

    def page_portfolio(self: Any) -> None:
        ttk.Label(self.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        account_id = self._require_account()
        if not account_id:
            return

        positions_response = self.client.get_positions(account_id)
        positions = items(positions_response, "securities", "positions")

        price_map = _last_price_map(self, positions)
        enriched_positions: list[dict[str, Any]] = []
        for position in positions:
            row = dict(position) if isinstance(position, dict) else {
                "ticker": field(position, "ticker", ""),
                "instrument_uid": field(position, "instrument_uid", field(position, "uid", "")),
                "balance": field(position, "balance", field(position, "quantity", 0)),
                "blocked_lots": field(position, "blocked_lots", field(position, "blocked", 0)),
                "average_position_price": field(position, "average_position_price", field(position, "average_price", None)),
                "expected_yield": field(position, "expected_yield", field(position, "expected_yield_fifo", None)),
                "currency": field(position, "currency", "RUB"),
            }
            uid = str(field(row, "instrument_uid", field(row, "uid", "")) or "")
            if uid in price_map:
                row["current_price"] = price_map[uid]
            enriched_positions.append(row)

        rows: list[tuple[Any, dict[str, Decimal | None]]] = []
        total_positions_value = Decimal("0")
        total_pnl: Decimal | None = Decimal("0")
        total_cost: Decimal = Decimal("0")
        pnl_known = False

        for position in enriched_positions:
            metrics = position_metrics(position)
            rows.append((position, metrics))
            total_positions_value += metrics["market_value"]
            pnl = metrics["pnl"]
            avg = metrics["average_price"]
            qty = metrics["quantity"]
            if pnl is not None:
                pnl_known = True
                total_pnl += pnl
            if avg is not None:
                total_cost += avg * qty

        if not pnl_known:
            total_pnl = None
        total_pnl_pct = (total_pnl / total_cost * Decimal("100")) if total_pnl is not None and total_cost != 0 else None

        try:
            portfolio = self.client.get_portfolio(account_id)
            summary = BalanceService.build_summary(positions_response, portfolio)
            balance_value = summary.cash
            currency = summary.currency or "RUB"
        except Exception:
            balance_value = Decimal("0")
            currency = "RUB"

        portfolio_value = balance_value + total_positions_value

        summary_frame = ttk.Frame(self.content)
        summary_frame.pack(fill="x", pady=(0, 12))
        for col in range(4):
            summary_frame.columnconfigure(col, weight=1)

        values = (
            ("Стоимость портфеля", format_money(portfolio_value, currency)),
            ("Стоимость позиций", format_money(total_positions_value, currency)),
            ("P&L", format_money(total_pnl, currency)),
            ("P&L %", "—" if total_pnl_pct is None else f"{total_pnl_pct:+.2f}%"),
        )
        for index, (title, value) in enumerate(values):
            frame = ttk.Frame(summary_frame, style="Card.TFrame", padding=14)
            frame.grid(row=0, column=index, sticky="nsew", padx=5)
            ttk.Label(frame, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(frame, text=value, style="CardValue.TLabel").pack(anchor="w", pady=(7, 0))

        ttk.Label(self.content, text=f"Позиции: {len(rows)} | Денежный баланс: {format_money(balance_value, currency)}").pack(anchor="w", pady=(0, 8))

        container = ttk.Frame(self.content)
        container.pack(fill="both", expand=True)

        columns = ("ticker", "quantity", "blocked", "average", "current", "value", "pnl", "pnl_pct")
        tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        headings = {
            "ticker": ("Тикер", 110),
            "quantity": ("Количество", 110),
            "blocked": ("Заблокировано", 125),
            "average": ("Средняя цена", 130),
            "current": ("Текущая цена", 130),
            "value": ("Стоимость", 140),
            "pnl": ("P&L", 130),
            "pnl_pct": ("P&L %", 100),
        }
        for column in columns:
            title, width = headings[column]
            tree.heading(column, text=title)
            tree.column(column, width=width, anchor="e" if column != "ticker" else "w")
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        position_by_iid: dict[str, Any] = {}
        for row_index, (position, metrics) in enumerate(rows):
            iid = f"position-{row_index}"
            position_by_iid[iid] = position
            ticker = str(field(position, "ticker", "") or "")
            blocked = decimal(field(position, "blocked_lots", field(position, "blocked", 0)))
            pnl = metrics["pnl"]
            pnl_pct = metrics["pnl_pct"]
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    ticker,
                    format_number(metrics["quantity"], 0),
                    format_number(blocked, 0),
                    format_money(metrics["average_price"], currency),
                    format_money(metrics["current_price"], currency),
                    format_money(metrics["market_value"], currency),
                    format_money(pnl, currency),
                    "—" if pnl_pct is None else f"{pnl_pct:+.2f}%",
                ),
            )

        actions = ttk.Frame(self.content)
        actions.pack(fill="x", pady=(10, 0))

        def selected_position() -> Any | None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("Портфель", "Выберите позицию.")
                return None
            return position_by_iid.get(selection[0])

        ttk.Button(actions, text="Продать", command=lambda: _sell(self, selected_position(), open_instrument)).pack(side="left")
        ttk.Button(actions, text="Открыть инструмент", command=lambda: _open(self, selected_position(), open_instrument)).pack(side="left", padx=8)
        tree.bind("<Double-1>", lambda _event: _open(self, selected_position(), open_instrument))

        self._portfolio_tree = tree

    def _sell(self: Any, position: Any | None, opener: Any) -> None:
        if position is None:
            return
        opener(self, position, "SELL")

    def _open(self: Any, position: Any | None, opener: Any) -> None:
        if position is None:
            return
        opener(self, position)

    app_class._page_portfolio = page_portfolio
    app_class._portfolio_page_v03_installed = True
