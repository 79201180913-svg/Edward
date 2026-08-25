from __future__ import annotations

from decimal import Decimal, InvalidOperation
from tkinter import messagebox, ttk
from typing import Any


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _items(value: Any, *names: str) -> list[Any]:
    if isinstance(value, list):
        return value
    for name in names:
        raw = _field(value, name, None)
        if raw is not None:
            return list(raw or [])
    return []


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _uid(value: Any) -> str:
    return str(_field(value, "instrument_uid", _field(value, "uid", "")) or "")


def _ticker(value: Any) -> str:
    return str(_field(value, "ticker", "") or "")


def _first_positive(value: Any, names: tuple[str, ...]) -> Decimal | None:
    for name in names:
        parsed = _decimal(_field(value, name, None))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _first_number(value: Any, names: tuple[str, ...]) -> Decimal | None:
    for name in names:
        parsed = _decimal(_field(value, name, None))
        if parsed is not None:
            return parsed
    return None


def calculate_pnl_row(source: Any, quantity: Decimal, current_price: Decimal) -> dict[str, Decimal | None]:
    average_price = _first_positive(
        source,
        ("average_position_price", "average_price", "avg_price", "average_buy_price"),
    )
    pnl = _first_number(source, ("expected_yield", "expected_yield_fifo", "pnl", "profit_loss"))

    if pnl is None and average_price is not None:
        pnl = (current_price - average_price) * quantity
    elif average_price is None and pnl is not None and quantity > 0:
        candidate = current_price - (pnl / quantity)
        if candidate > 0:
            average_price = candidate

    pnl_percent: Decimal | None = None
    if average_price is not None and average_price > 0 and quantity > 0 and pnl is not None:
        pnl_percent = pnl / (average_price * quantity) * Decimal("100")

    return {
        "average_price": average_price,
        "pnl": pnl,
        "pnl_percent": pnl_percent,
        "value": current_price * quantity,
    }


def _money(value: Decimal | None, currency: str) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ") + (f" {currency}" if currency else "")


def _find_tree(root: Any) -> ttk.Treeview | None:
    for child in root.winfo_children():
        if isinstance(child, ttk.Treeview):
            return child
        found = _find_tree(child)
        if found is not None:
            return found
    return None


def _widget_text(widget: Any) -> str:
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def _set_instrument_detail(app: Any, row: dict[str, Any]) -> None:
    detail = {
        "ticker": str(row.get("ticker", "")),
        "name": str(row.get("name", "") or row.get("ticker", "")),
        "currency": str(row.get("currency", "RUB") or "RUB").upper(),
        "last_price": str(row.get("current_price", "")),
        "uid": str(row.get("uid", "")),
        "instrument_uid": str(row.get("uid", "")),
        "instrument_kind": str(row.get("instrument_kind", "SHARE") or "SHARE"),
        "buy_available": bool(row.get("buy_available", True)),
        "sell_available": bool(row.get("sell_available", True)),
        "api_trade_available": True,
    }
    app.selected_instrument = dict(detail)
    app.instrument_detail = dict(detail)


def install_portfolio_pnl_fix(app_class: type[Any]) -> None:
    if getattr(app_class, "_portfolio_pnl_v03_fix_installed", False):
        return

    original_page = app_class._page_portfolio

    def page_portfolio(self: Any) -> None:
        original_page(self)
        aid = self._require_account()
        if not aid:
            return

        tree = _find_tree(self.content)
        if tree is None:
            return

        positions = _items(self.client.get_positions(aid), "securities", "positions")
        portfolio_positions = _items(self.client.get_portfolio(aid), "positions")
        by_uid = {_uid(item): item for item in positions if _uid(item)}
        by_ticker = {_ticker(item): item for item in positions if _ticker(item)}
        portfolio_by_uid = {_uid(item): item for item in portfolio_positions if _uid(item)}
        portfolio_by_ticker = {_ticker(item): item for item in portfolio_positions if _ticker(item)}

        columns = ("Тикер", "Количество", "Средняя цена", "Текущая цена", "Стоимость", "P&L", "P&L %")
        tree.configure(columns=columns)
        for column, width in zip(columns, (120, 120, 140, 140, 150, 140, 100)):
            tree.heading(column, text=column)
            tree.column(column, width=width, anchor="w")

        rows: list[dict[str, Any]] = []
        for item_id in tree.get_children():
            values = list(tree.item(item_id).get("values", []))
            tags = tree.item(item_id).get("tags", ())
            uid = str(tags[0]) if tags else ""
            ticker = str(values[0]) if values else ""
            quantity = _decimal(values[1] if len(values) > 1 else None) or Decimal("0")
            current_price = _decimal(values[3] if len(values) > 3 else None) or Decimal("0")
            source = portfolio_by_uid.get(uid) or by_uid.get(uid) or portfolio_by_ticker.get(ticker) or by_ticker.get(ticker) or {}
            currency = str(_field(source, "currency", "RUB") or "RUB").upper()
            kind = str(_field(source, "instrument_kind", _field(source, "instrument_type", "SHARE")) or "SHARE")
            name = str(_field(source, "name", ticker) or ticker)

            if current_price <= 0 and uid:
                try:
                    price_items = _items(self.client.get_last_prices([uid]), "last_prices")
                    if price_items:
                        current_price = _decimal(_field(price_items[0], "price", _field(price_items[0], "last_price", 0))) or Decimal("0")
                except Exception:
                    pass

            calc = calculate_pnl_row(source, quantity, current_price)
            row = {
                "ticker": ticker,
                "name": name,
                "uid": uid,
                "currency": currency,
                "instrument_kind": kind,
                "quantity": quantity,
                "current_price": current_price,
                "average_price": calc["average_price"],
                "pnl": calc["pnl"],
                "pnl_percent": calc["pnl_percent"],
                "value": calc["value"],
                "buy_available": True,
                "sell_available": True,
            }
            rows.append(row)
            tree.item(
                item_id,
                values=(
                    ticker,
                    f"{quantity:,.0f}".replace(",", " "),
                    _money(calc["average_price"], currency),
                    _money(current_price, currency),
                    _money(calc["value"], currency),
                    _money(calc["pnl"], currency),
                    f"{calc['pnl_percent']:+.2f}%" if calc["pnl_percent"] is not None else "—",
                ),
                tags=(uid,),
            )

        pnl_known = [row["pnl"] for row in rows if row["pnl"] is not None]
        value_total = sum((row["value"] for row in rows), Decimal("0"))
        pnl_total = sum(pnl_known, Decimal("0"))
        cost_known = [row for row in rows if row["average_price"] is not None]
        cost_total = sum((row["average_price"] * row["quantity"] for row in cost_known), Decimal("0"))
        pnl_pct_total = pnl_total / cost_total * Decimal("100") if cost_total > 0 and pnl_known else None

        # Remove the old summary cards by their actual Tk text option.
        for child in list(self.content.winfo_children()):
            if not isinstance(child, ttk.Frame):
                continue
            labels = [_widget_text(grandchild) for grandchild in child.winfo_children() if isinstance(grandchild, ttk.Label)]
            if any(label in {"Позиций", "Стоимость позиций", "P&L", "P&L %"} for label in labels):
                child.destroy()

        summary = ttk.Frame(self.content)
        summary.pack(fill="x", before=tree.master, pady=(0, 12))
        for i in range(4):
            summary.columnconfigure(i, weight=1)
        cards = (
            ("Позиций", str(len(rows))),
            ("Стоимость позиций", _money(value_total, "RUB")),
            ("P&L", _money(pnl_total, "RUB") if pnl_known else "—"),
            ("P&L %", f"{pnl_pct_total:+.2f}%" if pnl_pct_total is not None else "—"),
        )
        for index, (title, value) in enumerate(cards):
            card = ttk.Frame(summary, style="Card.TFrame", padding=12)
            card.grid(row=0, column=index, sticky="nsew", padx=4)
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(card, text=value, style="CardValue.TLabel").pack(anchor="w", pady=(6, 0))

        actions = None
        for child in self.content.winfo_children():
            if not isinstance(child, ttk.Frame):
                continue
            button_texts = [_widget_text(grandchild) for grandchild in child.winfo_children() if isinstance(grandchild, ttk.Button)]
            if "Открыть инструмент" in button_texts or "Продать" in button_texts:
                actions = child
                break
        if actions is None:
            actions = ttk.Frame(self.content)
            actions.pack(fill="x", pady=(10, 0))

        def selected_row() -> dict[str, Any] | None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("Портфель", "Выберите позицию.")
                return None
            uid = str(tree.item(selection[0]).get("tags", [""])[0])
            return next((row for row in rows if str(row["uid"]) == uid), None)

        def open_instrument() -> None:
            row = selected_row()
            if row is None or not row["uid"]:
                return
            _set_instrument_detail(self, row)
            self.show_page("instrument")

        def sell_selected() -> None:
            row = selected_row()
            if row is None or not row["uid"]:
                return
            _set_instrument_detail(self, row)
            if hasattr(self, "order_side_v03"):
                self.order_side_v03.set("SELL")
            if hasattr(self, "order_quantity_v03"):
                self.order_quantity_v03.set(str(int(row["quantity"])))
            self.show_page("instrument")

        for button in actions.winfo_children():
            if not isinstance(button, ttk.Button):
                continue
            text = _widget_text(button)
            if text == "Открыть инструмент":
                button.configure(command=open_instrument)
            elif text == "Продать":
                button.configure(command=sell_selected)

        tree.unbind("<Double-1>")
        tree.bind("<Double-1>", lambda _event: open_instrument(), add="+")

    app_class._page_portfolio = page_portfolio
    app_class._portfolio_pnl_v03_fix_installed = True
