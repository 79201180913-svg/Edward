from __future__ import annotations

from decimal import Decimal
from typing import Any
from tkinter import ttk
from edward.history.trading_history import TradeRecord


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


def _money(value: Any) -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ")


def _console(app: Any, message: str) -> None:
    print(message, flush=True)


def _security_fallback(positions: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in _items(positions, "securities"):
        uid = str(_field(item, "instrument_uid", ""))
        figi = str(_field(item, "figi", ""))
        key = uid or figi
        if key:
            result[key] = item
    return result


def _page_overview(app: Any) -> None:
    ttk.Label(app.content, text="Обзор счёта", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
    aid = app._require_account()
    if not aid:
        return
    positions = app.client.get_positions(aid)
    portfolio = app.client.get_portfolio(aid)
    summary = app.services_balance = __import__("edward.services.balance_service", fromlist=["BalanceService"]).BalanceService.build_summary(positions, portfolio)
    portfolio_positions = _items(portfolio, "positions")
    securities_fallback = _security_fallback(positions)

    securities_value = _decimal(_field(portfolio, "total_amount_shares"))
    securities_count = Decimal("0")
    for p in portfolio_positions:
        quantity = _decimal(_field(p, "quantity"))
        securities_count += quantity
        securities_value += Decimal("0") if securities_value != 0 else quantity * _decimal(_field(p, "current_price"))
    if securities_value == 0:
        for p in securities_fallback.values():
            securities_count += _decimal(_field(p, "balance")) + _decimal(_field(p, "blocked"))

    portfolio_value = _decimal(_field(portfolio, "total_amount_portfolio"))
    if portfolio_value == 0:
        portfolio_value = summary.portfolio_value

    cards = ttk.Frame(app.content)
    cards.pack(fill="x")
    for i in range(4):
        cards.columnconfigure(i, weight=1)
    values = (
        ("Баланс", summary.available, True),
        ("Стоимость бумаг", securities_value, True),
        ("Количество бумаг, шт.", securities_count, False),
        ("Стоимость портфеля", portfolio_value, True),
    )
    for i, (title, value, monetary) in enumerate(values):
        shown = f"{_money(value)} RUB" if monetary else f"{value:,.0f}".replace(",", " ")
        app._card(cards, title, shown, i)
    _console(app, f"[OVERVIEW] account_id={aid} balance={summary.available} securities={securities_value} securities_count={securities_count} portfolio={portfolio_value}")


def _page_portfolio(app: Any) -> None:
    ttk.Label(app.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
    aid = app._require_account()
    if not aid:
        return
    positions = app.client.get_positions(aid)
    portfolio = app.client.get_portfolio(aid)
    portfolio_positions = _items(portfolio, "positions")
    fallback = _security_fallback(positions)

    tree = app._tree(
        app.content,
        ("Тикер", "UID", "Количество, шт.", "Заблокировано заявками, шт.", "Цена 1 бумаги", "Стоимость", "Доходность"),
        (100, 330, 140, 210, 140, 150, 140),
    )

    by_uid: dict[str, Any] = {}
    for p in portfolio_positions:
        key = str(_field(p, "instrument_uid", "")) or str(_field(p, "figi", ""))
        if key:
            by_uid[key] = p

    # PortfolioPosition is authoritative for price/yield/quantity. PositionsSecurities
    # is the reliable fallback for quantity when sandbox portfolio is partially populated.
    merged_keys = list(dict.fromkeys(list(by_uid) + list(fallback)))
    for key in merged_keys:
        p = by_uid.get(key, {})
        s = fallback.get(key, {})
        quantity = _decimal(_field(p, "quantity"))
        blocked = _decimal(_field(p, "blocked_lots"))
        if quantity == 0:
            quantity = _decimal(_field(s, "balance")) + _decimal(_field(s, "blocked"))
        if blocked == 0:
            blocked = _decimal(_field(s, "blocked"))
        ticker = _field(p, "ticker", _field(s, "ticker", ""))
        uid = _field(p, "instrument_uid", _field(s, "instrument_uid", key))
        price = _decimal(_field(p, "current_price"))
        if price == 0 and uid:
            try:
                prices = _items(app.client.get_last_prices([str(uid)]), "last_prices")
                if prices:
                    price = _decimal(_field(prices[0], "price"))
            except Exception as exc:
                _console(app, f"[PORTFOLIO PRICE ERROR] uid={uid}: {exc}")
        value = quantity * price
        yield_value = _decimal(_field(p, "expected_yield"))
        tree.insert("", "end", values=(
            ticker,
            uid,
            f"{quantity:,.0f}".replace(",", " "),
            f"{blocked:,.0f}".replace(",", " "),
            _money(price),
            _money(value),
            f"{yield_value}%",
        ))

    if not merged_keys:
        ttk.Label(app.content, text="Ценных бумаг в портфеле нет.").pack(anchor="w", pady=12)
    _console(app, f"[PORTFOLIO] account_id={aid} portfolio_positions={len(portfolio_positions)} fallback_positions={len(fallback)} displayed={len(merged_keys)}")


def _status_text(raw: Any) -> str:
    text = str(raw).upper()
    mapping = {
        "1": "FILL",
        "2": "REJECTED",
        "3": "CANCELLED",
        "4": "NEW",
        "5": "PARTIALLYFILL",
        "EXECUTION_REPORT_STATUS_FILL": "FILL",
        "EXECUTION_REPORT_STATUS_REJECTED": "REJECTED",
        "EXECUTION_REPORT_STATUS_CANCELLED": "CANCELLED",
        "EXECUTION_REPORT_STATUS_NEW": "NEW",
        "EXECUTION_REPORT_STATUS_PARTIALLYFILL": "PARTIALLYFILL",
    }
    return mapping.get(text, text)


def _poll_orders(app: Any) -> None:
    for oid, meta in list(app.tracked_orders.items()):
        try:
            state = app.client.get_order_state(meta["account_id"], oid)
            status = _status_text(_field(state, "execution_report_status", _field(state, "status", "")))
            executed = int(_decimal(_field(state, "lots_executed", 0)))
            if status == "FILL":
                record = TradeRecord(
                    account_id=meta["account_id"], order_id=oid, instrument_uid=meta["instrument_uid"],
                    operation=meta["operation"], quantity=executed or int(meta["quantity"]), order_type=meta["order_type"],
                    execution_price=_decimal(_field(state, "executed_order_price", _field(state, "initial_security_price", None))),
                    amount=_decimal(_field(state, "total_order_amount", None)),
                    commission=_decimal(_field(state, "executed_commission", None)),
                    currency=str(_field(state, "currency", meta.get("currency", "RUB"))), status="FILLED",
                    figi=str(_field(state, "figi", "")), ticker=meta["ticker"], name=meta["name"],
                )
                app.history.save_completed(record)
                app.tracked_orders.pop(oid, None)
                _console(app, f"[ORDER FILLED] order_id={oid} ticker={meta['ticker']} lots={record.quantity}")
            elif status in {"REJECTED", "CANCELLED"}:
                record = TradeRecord(
                    account_id=meta["account_id"], order_id=oid, instrument_uid=meta["instrument_uid"],
                    operation=meta["operation"], quantity=int(meta["quantity"]), order_type=meta["order_type"],
                    execution_price=None, amount=None, commission=Decimal("0"),
                    currency=str(meta.get("currency", "RUB")), status="ERROR", ticker=meta["ticker"], name=meta["name"],
                )
                app.history.save(record)
                app.tracked_orders.pop(oid, None)
                _console(app, f"[ORDER FAILED] order_id={oid} ticker={meta['ticker']} status={status}")
            else:
                _console(app, f"[ORDER STATUS] order_id={oid} ticker={meta['ticker']} status={status} executed={executed}/{meta['quantity']}")
        except Exception as exc:
            _console(app, f"[POLL ERROR] order_id={oid}: {type(exc).__name__}: {exc}")


def install_final_fixes(app_class: type[Any]) -> None:
    app_class._page_overview = _page_overview
    app_class._page_portfolio = _page_portfolio
    app_class._poll_orders = _poll_orders
