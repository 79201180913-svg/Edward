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
    if isinstance(value, dict):
        if "units" in value or "nano" in value:
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        for key in ("value", "quantity", "balance", "blocked"):
            if key in value and value[key] is not value:
                return _decimal(value[key])
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _money(value: Any) -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ")


def _console(app: Any, message: str) -> None:
    print(message, flush=True)


def _security_records(positions: Any) -> list[Any]:
    return _items(positions, "securities")


def _security_index(positions: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in _security_records(positions):
        keys = (
            _field(item, "instrument_uid", ""),
            _field(item, "position_uid", ""),
            _field(item, "figi", ""),
            _field(item, "ticker", ""),
        )
        for key in keys:
            text = str(key or "")
            if text:
                result[text] = item
    return result


def _portfolio_key(position: Any) -> tuple[str, ...]:
    return tuple(
        str(_field(position, name, "") or "")
        for name in ("instrument_uid", "position_uid", "figi", "ticker")
    )


def _find_security(portfolio_position: Any, index: dict[str, Any]) -> Any:
    for key in _portfolio_key(portfolio_position):
        if key and key in index:
            return index[key]
    return None


def _position_quantity(portfolio_position: Any, security_position: Any) -> tuple[Decimal, Decimal, str]:
    quantity = _decimal(_field(portfolio_position, "quantity"))
    blocked_lots = _decimal(_field(portfolio_position, "blocked_lots"))

    fallback_balance = _decimal(_field(security_position, "balance")) if security_position is not None else Decimal("0")
    fallback_blocked = _decimal(_field(security_position, "blocked")) if security_position is not None else Decimal("0")

    # T-Invest contract:
    # PortfolioPosition.quantity = total quantity in pieces.
    # PositionsSecurities.balance = unlocked quantity in pieces.
    # PositionsSecurities.blocked = quantity locked by orders.
    if quantity <= 0:
        quantity = fallback_balance + fallback_blocked
    if blocked_lots <= 0:
        blocked_lots = fallback_blocked

    source = "PortfolioPosition.quantity" if _decimal(_field(portfolio_position, "quantity")) > 0 else "PositionsSecurities.balance+blocked"
    return quantity, blocked_lots, source


def _page_overview(app: Any) -> None:
    ttk.Label(app.content, text="Обзор счёта", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
    aid = app._require_account()
    if not aid:
        return

    positions = app.client.get_positions(aid)
    portfolio = app.client.get_portfolio(aid)
    summary = __import__("edward.services.balance_service", fromlist=["BalanceService"]).BalanceService.build_summary(positions, portfolio)
    portfolio_positions = _items(portfolio, "positions")
    security_index = _security_index(positions)

    securities_value = _decimal(_field(portfolio, "total_amount_shares"))
    securities_count = Decimal("0")
    for position in portfolio_positions:
        security = _find_security(position, security_index)
        quantity, _, _ = _position_quantity(position, security)
        securities_count += quantity

    portfolio_value = _decimal(_field(portfolio, "total_amount_portfolio"))
    if portfolio_value <= 0:
        portfolio_value = summary.available + securities_value

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

    _console(
        app,
        f"[OVERVIEW] account_id={aid} balance={summary.available} securities={securities_value} "
        f"securities_count={securities_count} api_total={_field(portfolio, 'total_amount_portfolio')} portfolio={portfolio_value}",
    )


def _page_portfolio(app: Any) -> None:
    ttk.Label(app.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
    aid = app._require_account()
    if not aid:
        return

    positions = app.client.get_positions(aid)
    portfolio = app.client.get_portfolio(aid)
    portfolio_positions = _items(portfolio, "positions")
    security_index = _security_index(positions)

    tree = app._tree(
        app.content,
        ("Тикер", "UID", "Количество, шт.", "Заблокировано заявками, шт.", "Цена 1 бумаги", "Стоимость", "Доходность"),
        (100, 330, 140, 210, 140, 150, 140),
    )

    # First use the positions returned by GetSandboxPortfolio/GetPortfolio.
    # Then enrich each row from GetSandboxPositions because sandbox may omit or
    # zero-fill PortfolioPosition.quantity while PositionsSecurities has the
    # authoritative balance/blocked split.
    for position in portfolio_positions:
        security = _find_security(position, security_index)
        quantity, blocked, quantity_source = _position_quantity(position, security)
        ticker = str(_field(position, "ticker", "") or _field(security, "ticker", ""))
        uid = str(_field(position, "instrument_uid", "") or _field(security, "instrument_uid", ""))
        figi = str(_field(position, "figi", "") or _field(security, "figi", ""))
        price = _decimal(_field(position, "current_price"))
        if price <= 0 and uid:
            try:
                prices = _items(app.client.get_last_prices([uid]), "last_prices")
                if prices:
                    price = _decimal(_field(prices[0], "price"))
            except Exception as exc:
                _console(app, f"[PORTFOLIO PRICE ERROR] uid={uid}: {exc}")
        value = quantity * price
        yield_value = _decimal(_field(position, "expected_yield", _field(position, "expected_yield_fifo", 0)))

        tree.insert(
            "",
            "end",
            values=(
                ticker,
                uid or figi,
                f"{quantity:,.0f}".replace(",", " "),
                f"{blocked:,.0f}".replace(",", " "),
                _money(price),
                _money(value),
                f"{yield_value}%",
            ),
        )
        _console(
            app,
            f"[PORTFOLIO POSITION] ticker={ticker} uid={uid or figi} "
            f"quantity={quantity} blocked={blocked} source={quantity_source} "
            f"balance={_field(security, 'balance', None)} security_blocked={_field(security, 'blocked', None)}",
        )

    if not portfolio_positions:
        ttk.Label(app.content, text="Ценных бумаг в портфеле нет.").pack(anchor="w", pady=12)

    _console(
        app,
        f"[PORTFOLIO] account_id={aid} portfolio_positions={len(portfolio_positions)} "
        f"sandbox_security_positions={len(_security_records(positions))}",
    )


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
            executed = int(_decimal(_field(state, "lots_executed", _field(state, "quantity_executed", 0))))
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
