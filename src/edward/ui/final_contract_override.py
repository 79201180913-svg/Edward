from __future__ import annotations

from decimal import Decimal
from typing import Any
from tkinter import ttk


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _items(value: Any, name: str) -> list[Any]:
    if isinstance(value, list):
        return value
    raw = _field(value, name, [])
    return list(raw or [])


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _is_cash(position: Any) -> bool:
    ticker = str(_field(position, "ticker", "") or "").upper()
    figi = str(_field(position, "figi", "") or "").upper()
    currency = str(_field(position, "currency", "") or "").upper()
    instrument_type = str(_field(position, "instrument_type", _field(position, "instrument_kind", "")) or "").upper()
    return ticker == "RUB000UTSTOM" or figi == "RUB000UTSTOM" or ticker.startswith("RUB") or (
        currency == "RUB" and instrument_type in {"CURRENCY", "INSTRUMENT_TYPE_CURRENCY"}
    )


def _uid(value: Any) -> str:
    return str(_field(value, "instrument_uid", _field(value, "uid", "")) or "")


def _money(value: Any) -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ") + " RUB"


def _snapshot(client: Any, account_id: str) -> tuple[Decimal, Decimal, Decimal, list[dict[str, Any]]]:
    positions = client.get_positions(account_id)
    portfolio = client.get_portfolio(account_id)
    money = _items(positions, "money")
    cash = sum((_decimal(_field(m, "available", _field(m, "available_value", 0))) for m in money), Decimal("0"))
    security_map = {_uid(s): s for s in _items(positions, "securities") if _uid(s) and not _is_cash(s)}
    rows: list[dict[str, Any]] = []
    for p in _items(portfolio, "positions"):
        if _is_cash(p):
            continue
        uid = _uid(p)
        sec = security_map.get(uid, {})
        quantity = _decimal(_field(p, "quantity", 0))
        if quantity <= 0:
            quantity = _decimal(_field(sec, "balance", 0)) + _decimal(_field(sec, "blocked", 0))
        if quantity <= 0:
            continue
        blocked = _decimal(_field(p, "blocked_lots", 0))
        if blocked <= 0:
            blocked = _decimal(_field(sec, "blocked", 0))
        price = _decimal(_field(p, "current_price", 0))
        if price <= 0 and uid:
            try:
                prices = _items(client.get_last_prices([uid]), "last_prices")
                if prices:
                    price = _decimal(_field(prices[0], "price", _field(prices[0], "last_price", 0)))
            except Exception:
                pass
        rows.append({
            "ticker": str(_field(p, "ticker", _field(sec, "ticker", "")) or ""),
            "uid": uid,
            "quantity": quantity,
            "blocked": blocked,
            "price": price,
            "value": quantity * price,
            "yield": _decimal(_field(p, "expected_yield", _field(p, "expected_yield_fifo", 0))),
        })
    securities = sum((r["value"] for r in rows), Decimal("0"))
    api_total = _decimal(_field(portfolio, "total_amount_portfolio", 0))
    total = api_total if api_total > 0 else cash + securities
    print(f"[PORTFOLIO SNAPSHOT FINAL] account_id={account_id} cash={cash} securities={securities} api_total={api_total} total={total} rows={len(rows)}", flush=True)
    return cash, securities, total, rows


def install_final_contract_override(EdwardApp: Any) -> None:
    def _page_overview(self: Any) -> None:
        ttk.Label(self.content, text="Обзор счёта", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        aid = self._require_account()
        if not aid:
            return
        cash, securities, total, rows = _snapshot(self.client, aid)
        cards = ttk.Frame(self.content)
        cards.pack(fill="x")
        for i in range(4):
            cards.columnconfigure(i, weight=1)
        values = (("Баланс", cash, True), ("Стоимость бумаг", securities, True), ("Количество бумаг, шт.", sum(r["quantity"] for r in rows), False), ("Стоимость портфеля", total, True))
        for i, (title, value, monetary) in enumerate(values):
            shown = f"{value:,.0f}".replace(",", " ") if not monetary else _money(value)
            self._card(cards, title, shown, i)
        print(f"[OVERVIEW FINAL] account_id={aid} balance={cash} securities={securities} count={sum(r['quantity'] for r in rows)} portfolio={total}", flush=True)

    def _page_portfolio(self: Any) -> None:
        ttk.Label(self.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        aid = self._require_account()
        if not aid:
            return
        cash, securities, total, rows = _snapshot(self.client, aid)
        ttk.Label(self.content, text=f"Стоимость портфеля: {_money(total)} | Баланс: {_money(cash)}").pack(anchor="w", pady=(0, 10))
        tree = self._tree(self.content, ("Тикер", "UID", "Количество, шт.", "Заблокировано заявками, шт.", "Цена 1 бумаги", "Стоимость", "Доходность"), (110, 340, 140, 210, 140, 150, 140))
        if not rows:
            ttk.Label(self.content, text="Ценных бумаг в портфеле нет.").pack(anchor="w", pady=12)
        for r in rows:
            tree.insert("", "end", values=(r["ticker"], r["uid"], f"{r['quantity']:,.0f}".replace(",", " "), f"{r['blocked']:,.0f}".replace(",", " "), _money(r["price"]), _money(r["value"]), f"{r['yield']}"))
        print(f"[PORTFOLIO FINAL] account_id={aid} positions={len(rows)} securities={securities} total={total}", flush=True)

    EdwardApp._page_overview = _page_overview
    EdwardApp._page_portfolio = _page_portfolio
