from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from tkinter import messagebox, ttk
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.balance_service import BalanceService

_SENTINEL = "__edward_contract_ui_fixes_installed__"


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


def _money(app: Any, value: Any, currency: str = "RUB") -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ") + f" {currency}"


def _uid(value: Any) -> str:
    return str(_field(value, "instrument_uid", _field(value, "uid", "")))


def _build_security_rows(client: Any, account_id: str) -> tuple[list[dict[str, Any]], Decimal]:
    positions = client.get_positions(account_id)
    portfolio = client.get_portfolio(account_id)

    securities = _items(positions, "securities")
    portfolio_positions = _items(portfolio, "positions")
    by_uid = {_uid(item): item for item in securities if _uid(item)}

    rows: list[dict[str, Any]] = []
    for position in portfolio_positions:
        uid = _uid(position)
        fallback = by_uid.get(uid, {})
        quantity = _decimal(_field(position, "quantity", 0))
        if quantity == 0:
            quantity = _decimal(_field(fallback, "balance", 0)) + _decimal(_field(fallback, "blocked", 0))

        blocked = _decimal(_field(position, "blocked_lots", 0))
        if blocked == 0:
            blocked = _decimal(_field(fallback, "blocked", 0))

        price = _decimal(_field(position, "current_price", 0))
        ticker = str(_field(position, "ticker", _field(fallback, "ticker", "")))
        figi = str(_field(position, "figi", _field(fallback, "figi", "")))

        if price <= 0 and uid:
            try:
                price_response = client.get_last_prices([uid])
                prices = _items(price_response, "last_prices")
                if prices:
                    price = _decimal(_field(prices[0], "price", _field(prices[0], "last_price", 0)))
            except Exception:
                pass

        value = quantity * price
        yield_value = _decimal(_field(position, "expected_yield", _field(position, "expected_yield_fifo", 0)))
        rows.append(
            {
                "ticker": ticker,
                "uid": uid,
                "figi": figi,
                "quantity": quantity,
                "blocked": blocked,
                "price": price,
                "value": value,
                "yield": yield_value,
            }
        )

    return rows, sum((row["value"] for row in rows), Decimal("0"))


def _portfolio_snapshot(client: Any, account_id: str) -> tuple[Decimal, Decimal, Decimal, Any]:
    positions = client.get_positions(account_id)
    portfolio = client.get_portfolio(account_id)
    summary = BalanceService.build_summary(positions, portfolio)
    rows, securities_value = _build_security_rows(client, account_id)

    # In the current SANDBOX UI the contract-correct portfolio total is the
    # available cash plus the value of held securities. This avoids showing a
    # duplicated cash amount when the sandbox aggregate is inconsistent.
    calculated_total = summary.available + securities_value
    api_total = _decimal(_field(portfolio, "total_amount_portfolio", 0))

    print(
        f"[PORTFOLIO SNAPSHOT] account_id={account_id} available={summary.available} "
        f"securities={securities_value} api_total={api_total} calculated_total={calculated_total}",
        flush=True,
    )
    return summary.available, securities_value, calculated_total, rows


def _install_client_history_normalization() -> None:
    original = TInvestAdapterClient.get_operations
    if getattr(TInvestAdapterClient, "_edward_operations_normalized", False):
        return

    def normalized(self: TInvestAdapterClient, account_id: str, limit: int = 1000) -> dict[str, Any]:
        response = original(self, account_id, limit)
        if not isinstance(response, dict):
            return {"operations": []}
        operations = _items(response, "operations", "items")
        normalized_response = dict(response)
        normalized_response["operations"] = operations
        normalized_response["items"] = operations
        print(f"[HISTORY NORMALIZED] account_id={account_id} operations={len(operations)}", flush=True)
        return normalized_response

    TInvestAdapterClient.get_operations = normalized
    setattr(TInvestAdapterClient, "_edward_operations_normalized", True)


def _install_pages(EdwardApp: Any) -> None:
    def _page_overview(self: Any) -> None:
        ttk.Label(self.content, text="Обзор счёта", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        aid = self._require_account()
        if not aid:
            return

        cash, securities, total, rows = _portfolio_snapshot(self.client, aid)
        currency = "RUB"
        cards = ttk.Frame(self.content)
        cards.pack(fill="x")
        for i in range(4):
            cards.columnconfigure(i, weight=1)

        values = (("Баланс", cash), ("Стоимость бумаг", securities), ("Количество бумаг, шт.", sum(r["quantity"] for r in rows)), ("Стоимость портфеля", total))
        for i, (title, value) in enumerate(values):
            shown = f"{value:,.0f}".replace(",", " ") if i == 2 else _money(self, value, currency)
            self._card(cards, title, shown, i)

        active = self.context.active_account
        details = ttk.Frame(self.content)
        details.pack(fill="x", pady=(28, 0))
        for r, (key, value) in enumerate((("ID счёта", aid), ("Название", _field(active, "name", "") if active else ""), ("Статус", _field(active, "status", "") if active else ""))):
            ttk.Label(details, text=key, width=22).grid(row=r, column=0, sticky="w", pady=4)
            ttk.Label(details, text=value).grid(row=r, column=1, sticky="w", pady=4)

        print(f"[OVERVIEW] account_id={aid} balance={cash} securities={securities} securities_count={sum(r['quantity'] for r in rows)} portfolio={total}", flush=True)

    def _page_portfolio(self: Any) -> None:
        ttk.Label(self.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        aid = self._require_account()
        if not aid:
            return

        cash, securities_value, total, rows = _portfolio_snapshot(self.client, aid)
        ttk.Label(self.content, text=f"Стоимость портфеля: {_money(self, total)} | Баланс: {_money(self, cash)}").pack(anchor="w", pady=(0, 10))

        tree = self._tree(
            self.content,
            ("Тикер", "UID", "Количество, шт.", "Заблокировано заявками, шт.", "Цена 1 бумаги", "Стоимость", "Доходность"),
            (110, 340, 140, 200, 140, 150, 140),
        )

        if not rows:
            ttk.Label(self.content, text="Ценных бумаг в портфеле нет.").pack(anchor="w", pady=12)
            print(f"[PORTFOLIO] account_id={aid} positions=0", flush=True)
            return

        for row in rows:
            tree.insert("", "end", values=(
                row["ticker"],
                row["uid"] or row["figi"],
                f"{row['quantity']:,.0f}".replace(",", " "),
                f"{row['blocked']:,.0f}".replace(",", " "),
                _money(self, row["price"], "RUB"),
                _money(self, row["value"], "RUB"),
                f"{row['yield']}",
            ))

        print(f"[PORTFOLIO] account_id={aid} positions={len(rows)} securities={securities_value} total={total}", flush=True)

    def _page_history(self: Any) -> None:
        ttk.Label(self.content, text="История операций", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        aid = self._require_account()
        if not aid:
            return

        cash, securities, total, _rows = _portfolio_snapshot(self.client, aid)
        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Обновить историю", command=self.refresh_current).pack(side="left")

        tree = self._tree(
            self.content,
            ("Дата", "Время", "Счёт", "Тип", "Статус", "Сумма", "Валюта", "Текущий баланс", "Стоимость портфеля", "Инструмент", "Количество", "Операция ID"),
            (100, 85, 280, 170, 110, 130, 80, 140, 150, 140, 100, 360),
        )
        ttk.Button(toolbar, text="Копировать всю историю", command=lambda: _copy_rows(self, tree, False)).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Копировать выбранное", command=lambda: _copy_rows(self, tree, True)).pack(side="left")
        ttk.Label(toolbar, text=f"Баланс: {_money(self, cash)} | Портфель: {_money(self, total)}").pack(side="left", padx=15)

        seen: set[str] = set()
        try:
            response = self.client.get_operations(aid, 1000)
            operations = _items(response, "operations", "items")
        except Exception as exc:
            print(f"[HISTORY API ERROR] {type(exc).__name__}: {exc}", flush=True)
            operations = []
            self._show_error(exc, "получение истории операций")

        def state_text(value: Any) -> str:
            mapping = {0: "Не определён", 1: "Успех", 2: "Ошибка", 3: "В процессе"}
            if isinstance(value, int):
                return mapping.get(value, "В процессе")
            text = str(value).upper()
            if any(x in text for x in ("CANCEL", "REJECT", "ERROR", "FAIL")):
                return "Ошибка"
            if any(x in text for x in ("EXECUTED", "FILL", "SUCCESS")):
                return "Успех"
            return "В процессе"

        def type_text(value: Any) -> str:
            mapping = {1: "Пополнение", 15: "Покупка", 16: "Покупка", 19: "Комиссия", 22: "Продажа", 70: "Фандинг"}
            if isinstance(value, int):
                return mapping.get(value, f"Операция #{value}")
            text = str(value).upper()
            mapping_text = {"OPERATION_TYPE_INPUT": "Пополнение", "OPERATION_TYPE_FUNDING": "Фандинг", "OPERATION_TYPE_BUY": "Покупка", "OPERATION_TYPE_BUY_CARD": "Покупка", "OPERATION_TYPE_SELL": "Продажа", "OPERATION_TYPE_SELL_CARD": "Продажа", "OPERATION_TYPE_BROKER_FEE": "Комиссия", "OPERATION_TYPE_SERVICE_FEE": "Сервисная комиссия"}
            return mapping_text.get(text, text.replace("OPERATION_TYPE_", "").replace("_", " ").title() or "Операция")

        def add_api(operation: Any) -> None:
            operation_id = str(_field(operation, "id", _field(operation, "operation_id", "")))
            if operation_id:
                seen.add(operation_id)
            timestamp = _field(operation, "date", _field(operation, "timestamp", _field(operation, "execution_time", "")))
            date_text, time_text = "", ""
            if timestamp:
                try:
                    dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                    if dt.tzinfo:
                        dt = dt.astimezone(timezone.utc)
                    date_text, time_text = dt.strftime("%d.%m.%Y"), dt.strftime("%H:%M:%S")
                except Exception:
                    parts = str(timestamp).split("T", 1)
                    date_text, time_text = parts[0], parts[1][:8] if len(parts) > 1 else ""

            money = _field(operation, "payment", _field(operation, "amount", ""))
            currency = str(_field(money, "currency", _field(operation, "currency", "RUB"))).upper()
            instrument = str(_field(operation, "ticker", _field(operation, "instrument_uid", _field(operation, "figi", ""))))
            quantity = _field(operation, "quantity_done", _field(operation, "quantity", ""))
            tree.insert("", "end", values=(date_text, time_text, aid, type_text(_field(operation, "operation_type", _field(operation, "type", ""))), state_text(_field(operation, "state", _field(operation, "status", ""))), _money(self, money, "") if money not in (None, "") else "", currency, _money(self, cash), _money(self, total), instrument, quantity, operation_id))

        for operation in operations:
            add_api(operation)

        local_added = 0
        for row in self.history.read_all():
            operation_id = str(row.get("order_id", ""))
            if operation_id and operation_id in seen:
                continue
            local_added += 1
            status = str(row.get("status", "")).upper()
            status_text_local = "Успех" if status == "FILLED" else "Ошибка" if status in {"ERROR", "FAILED", "CANCELED", "CANCELLED"} else "В процессе"
            tree.insert("", "end", values=(row.get("date", ""), row.get("time", ""), row.get("account_id", aid), row.get("operation", ""), status_text_local, row.get("amount", ""), row.get("currency", ""), _money(self, cash), _money(self, total), row.get("ticker", ""), row.get("quantity", ""), operation_id))

        print(f"[HISTORY] api={len(operations)} local_added={local_added} total={len(operations) + local_added}", flush=True)

    def _copy_rows(app: Any, tree: Any, selected_only: bool = False) -> None:
        items = tree.selection() if selected_only else tree.get_children("")
        columns = [tree.heading(column, "text") for column in tree["columns"]]
        lines = ["\t".join(columns)]
        for item in items:
            lines.append("\t".join(str(value) for value in tree.item(item, "values")))
        if len(lines) <= 1:
            messagebox.showinfo("Edward", "Нет строк для копирования.", parent=app)
            return
        app.clipboard_clear()
        app.clipboard_append("\n".join(lines))
        app.update()
        app.status_var.set(f"Скопировано строк: {len(lines) - 1}")

    EdwardApp._page_overview = _page_overview
    EdwardApp._page_portfolio = _page_portfolio
    EdwardApp._page_history = _page_history


def install_contract_ui_fixes(EdwardApp: Any) -> None:
    if getattr(EdwardApp, _SENTINEL, False):
        return
    _install_client_history_normalization()
    _install_pages(EdwardApp)
    setattr(EdwardApp, _SENTINEL, True)
