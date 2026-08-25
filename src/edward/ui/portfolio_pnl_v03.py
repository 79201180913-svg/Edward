from __future__ import annotations

from decimal import Decimal
from tkinter import messagebox, ttk
from typing import Any


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


def _money(value: Any, currency: str = "") -> str:
    text = f"{_decimal(value):,.2f}".replace(",", " ")
    return f"{text} {currency}".strip()


def _items(value: Any, *names: str) -> list[Any]:
    if isinstance(value, list):
        return value
    for name in names:
        raw = _field(value, name, None)
        if raw is not None:
            return list(raw or [])
    return []


def _uid(position: Any) -> str:
    return str(_field(position, "instrument_uid", _field(position, "uid", "")) or "")


def _ticker(position: Any) -> str:
    return str(_field(position, "ticker", "") or "")


def _quantity(position: Any) -> Decimal:
    for name in ("quantity", "balance", "quantity_lots"):
        value = _decimal(_field(position, name, 0))
        if value != 0:
            return abs(value)
    return Decimal("0")


def _price(position: Any) -> Decimal:
    for name in ("current_price", "last_price", "price"):
        value = _decimal(_field(position, name, 0))
        if value > 0:
            return value
    return Decimal("0")


def _pnl(position: Any) -> Decimal:
    for name in ("expected_yield", "expected_yield_fifo", "pnl", "profit_loss"):
        raw = _field(position, name, None)
        if raw is not None:
            return _decimal(raw)
    return Decimal("0")


def _average_price(position: Any, quantity: Decimal, current_price: Decimal, pnl: Decimal) -> Decimal:
    for name in ("average_position_price", "average_price", "avg_price", "average_buy_price"):
        value = _decimal(_field(position, name, 0))
        if value > 0:
            return value
    if quantity > 0 and current_price > 0 and pnl != 0:
        candidate = current_price - (pnl / quantity)
        if candidate > 0:
            return candidate
    return Decimal("0")


def install_portfolio_pnl(app_class: type[Any]) -> None:
    if getattr(app_class, "_portfolio_pnl_v03_installed", False):
        return

    original_page = app_class._page_portfolio

    def page_portfolio(self: Any) -> None:
        original_page(self)

        aid = self._require_account()
        if not aid:
            return

        # The existing page owns the final Treeview. Find it rather than
        # replacing the existing quantity calculation layer.
        tree = None
        for child in self.content.winfo_children():
            if isinstance(child, ttk.Frame):
                for nested in child.winfo_children():
                    if isinstance(nested, ttk.Treeview):
                        tree = nested
                        break
            if tree is not None:
                break
        if tree is None:
            return

        positions_response = self.client.get_positions(aid)
        portfolio_response = self.client.get_portfolio(aid)
        positions = _items(positions_response, "securities", "positions")
        portfolio_positions = _items(portfolio_response, "positions")
        by_uid = {_uid(item): item for item in positions if _uid(item)}

        rows: list[dict[str, Any]] = []
        for source in portfolio_positions + positions:
            uid = _uid(source)
            ticker = _ticker(source)
            if not uid and not ticker:
                continue
            quantity = _quantity(source)
            if quantity <= 0:
                continue
            current_price = _price(source)
            if current_price <= 0 and uid:
                try:
                    prices = _items(self.client.get_last_prices([uid]), "last_prices")
                    if prices:
                        current_price = _decimal(_field(prices[0], "price", _field(prices[0], "last_price", 0)))
                except Exception:
                    pass
            pnl = _pnl(source)
            average_price = _average_price(source, quantity, current_price, pnl)
            value = quantity * current_price
            pnl_percent = (pnl / (average_price * quantity) * Decimal("100")) if average_price > 0 and quantity > 0 else Decimal("0")
            currency = str(_field(source, "currency", "RUB") or "RUB").upper()
            rows.append({
                "uid": uid,
                "ticker": ticker,
                "quantity": quantity,
                "average_price": average_price,
                "current_price": current_price,
                "value": value,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "currency": currency,
                "source": source,
            })

        # De-duplicate the same position returned by the two endpoints.
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = row["uid"] or row["ticker"]
            unique[key] = row
        rows = list(unique.values())

        pnl_total = sum((r["pnl"] for r in rows), Decimal("0"))
        value_total = sum((r["value"] for r in rows), Decimal("0"))
        cost_total = sum((r["average_price"] * r["quantity"] for r in rows), Decimal("0"))
        pnl_percent_total = (pnl_total / cost_total * Decimal("100")) if cost_total > 0 else Decimal("0")

        summary = ttk.Frame(self.content)
        summary.pack(fill="x", before=tree.master, pady=(0, 12))
        for i in range(4):
            summary.columnconfigure(i, weight=1)

        cards = (
            ("Позиций", str(len(rows))),
            ("Стоимость позиций", _money(value_total, "RUB")),
            ("P&L", _money(pnl_total, "RUB")),
            ("P&L %", f"{pnl_percent_total:+.2f}%"),
        )
        for idx, (title, value) in enumerate(cards):
            card = ttk.Frame(summary, style="Card.TFrame", padding=12)
            card.grid(row=0, column=idx, sticky="nsew", padx=4)
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(card, text=value, style="CardValue.TLabel").pack(anchor="w", pady=(6, 0))

        # Replace the old presentation headers while keeping the existing tree
        # object and data lifecycle.
        columns = ("Тикер", "Количество", "Средняя цена", "Текущая цена", "Стоимость", "P&L", "P&L %")
        old_children = tree.get_children()
        for item in old_children:
            tree.delete(item)
        tree.configure(columns=columns)
        widths = (120, 120, 140, 140, 150, 140, 100)
        for column, width in zip(columns, widths):
            tree.heading(column, text=column)
            tree.column(column, width=width, anchor="w")

        for row in rows:
            tree.insert(
                "",
                "end",
                values=(
                    row["ticker"],
                    f"{row['quantity']:,.0f}".replace(",", " "),
                    _money(row["average_price"], row["currency"]) if row["average_price"] > 0 else "—",
                    _money(row["current_price"], row["currency"]) if row["current_price"] > 0 else "—",
                    _money(row["value"], row["currency"]),
                    f"{row['pnl']:+,.2f}".replace(",", " ") + (f" {row['currency']}" if row["currency"] else ""),
                    f"{row['pnl_percent']:+.2f}%" if row["average_price"] > 0 else "—",
                ),
                tags=(row["uid"],),
            )

        actions = ttk.Frame(self.content)
        actions.pack(fill="x", pady=(10, 0))

        def selected_row() -> dict[str, Any] | None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("Портфель", "Выберите позицию.")
                return None
            uid = str(tree.item(selection[0]).get("tags", [""])[0])
            return next((r for r in rows if str(r["uid"]) == uid), None)

        def sell_selected() -> None:
            row = selected_row()
            if row is None:
                return
            if not row["uid"]:
                messagebox.showwarning("Портфель", "Для этой позиции отсутствует UID инструмента.")
                return
            self.selected_instrument = {
                "ticker": row["ticker"],
                "name": row["ticker"],
                "currency": row["currency"],
                "last_price": str(row["current_price"]),
                "uid": row["uid"],
                "instrument_uid": row["uid"],
                "instrument_kind": "SHARE",
                "sell_available": True,
                "buy_available": False,
                "api_trade_available": True,
            }
            self.show_page("order")

        def open_instrument() -> None:
            row = selected_row()
            if row is None or not row["uid"]:
                return
            self.selected_instrument = {
                "ticker": row["ticker"],
                "name": row["ticker"],
                "currency": row["currency"],
                "last_price": str(row["current_price"]),
                "uid": row["uid"],
                "instrument_uid": row["uid"],
                "instrument_kind": "SHARE",
                "sell_available": True,
                "buy_available": True,
                "api_trade_available": True,
            }
            self.show_page("instrument")

        ttk.Button(actions, text="Продать", command=sell_selected).pack(side="left")
        ttk.Button(actions, text="Открыть инструмент", command=open_instrument).pack(side="left", padx=8)

    app_class._page_portfolio = page_portfolio
    app_class._portfolio_pnl_v03_installed = True
