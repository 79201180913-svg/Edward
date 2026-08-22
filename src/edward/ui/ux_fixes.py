from __future__ import annotations

from decimal import Decimal
from tkinter import messagebox, ttk
from typing import Any

from edward.history.trading_history import TradeRecord
from edward.services.balance_service import BalanceService
from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.validation.trading_validator import TradingValidator


_SENTINEL = "__edward_ux_fixes_installed__"


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


def _text(value: Any) -> str:
    return str(value) if value not in (None, "") else ""


def _money(value: Any) -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ")


def _lot_size(client: Any, instrument_uid: str) -> Decimal:
    try:
        instrument = client.get_instrument(instrument_uid)
        lot = _field(instrument, "lot", _field(instrument, "lot_size", 1))
        value = _decimal(lot)
        return value if value > 0 else Decimal("1")
    except Exception:
        return Decimal("1")


def _load_current_price(client: Any, instrument_uid: str, instrument: Any) -> Decimal:
    """Get a usable current price without turning a missing price into 0."""
    selected_price = _decimal(instrument.get("last_price")) if isinstance(instrument, dict) else Decimal("0")
    if selected_price > 0:
        return selected_price

    try:
        response = client.get_last_prices([instrument_uid])
        prices = _items(response, "last_prices")
        if prices:
            price = _decimal(_field(prices[0], "price", _field(prices[0], "last_price", None)))
            if price > 0:
                _console(None, f"[ORDER PRICE] uid={instrument_uid} source=last_prices price={price}")
                return price
    except Exception as exc:
        _console(None, f"[ORDER PRICE] uid={instrument_uid} last_prices_error={type(exc).__name__}: {exc}")

    _console(None, f"[ORDER PRICE] uid={instrument_uid} source=unavailable price=0")
    return Decimal("0")


def _append_history_error(app: Any, request: OrderRequest, ticker: str, name: str, error: Exception, price: Decimal | None = None, amount: Decimal | None = None) -> None:
    try:
        app.history.save(
            TradeRecord(
                account_id=request.account_id,
                order_id=request.request_id,
                instrument_uid=request.instrument_uid,
                operation=request.side.value,
                quantity=request.quantity,
                order_type=request.order_type.value,
                execution_price=price,
                amount=amount,
                commission=Decimal("0"),
                currency="RUB",
                status="ERROR",
                ticker=ticker,
                name=name,
            )
        )
    except Exception as history_error:
        _console(app, f"[HISTORY ERROR] Не удалось записать неуспешную операцию: {type(history_error).__name__}: {history_error}")


def _console(app: Any, message: str) -> None:
    print(message, flush=True)


def _page_overview(app: Any) -> None:
    ttk.Label(app.content, text="Обзор счёта", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
    aid = app._require_account()
    if not aid:
        _console(app, "[OVERVIEW] Нет активного счёта")
        return

    positions = app.client.get_positions(aid)
    portfolio = app.client.get_portfolio(aid)
    summary = BalanceService.build_summary(positions, portfolio)
    portfolio_positions = _items(portfolio, "positions")

    securities_value = _decimal(_field(portfolio, "total_amount_shares"))
    if securities_value == 0:
        for position in portfolio_positions:
            securities_value += _decimal(_field(position, "current_price")) * _decimal(_field(position, "quantity"))

    securities_count = sum(_decimal(_field(p, "quantity")) for p in portfolio_positions)
    portfolio_value = _decimal(_field(portfolio, "total_amount_portfolio"))
    if portfolio_value == 0:
        portfolio_value = summary.portfolio_value

    currency = summary.currency or "RUB"
    cards = ttk.Frame(app.content)
    cards.pack(fill="x")
    for i in range(4):
        cards.columnconfigure(i, weight=1)
    values = (
        ("Баланс", summary.available),
        ("Стоимость бумаг", securities_value),
        ("Количество бумаг, шт.", securities_count),
        ("Стоимость портфеля", portfolio_value),
    )
    for i, (title, value) in enumerate(values):
        shown = f"{_money(value)} {currency}" if i != 2 else f"{value:,.0f}".replace(",", " ")
        app._card(cards, title, shown, i)

    active = app.context.active_account
    details = ttk.Frame(app.content)
    details.pack(fill="x", pady=(28, 0))
    rows = (("ID счёта", aid), ("Название", _field(active, "name", "") if active else ""), ("Статус", _field(active, "status", "") if active else ""))
    for r, (key, value) in enumerate(rows):
        ttk.Label(details, text=key, width=22).grid(row=r, column=0, sticky="w", pady=4)
        ttk.Label(details, text=value).grid(row=r, column=1, sticky="w", pady=4)

    _console(app, f"[OVERVIEW] account_id={aid} balance={summary.available} securities={securities_value} securities_count={securities_count} portfolio={portfolio_value}")


def _page_portfolio(app: Any) -> None:
    ttk.Label(app.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
    aid = app._require_account()
    if not aid:
        _console(app, "[PORTFOLIO] Нет активного счёта")
        return

    positions = app.client.get_positions(aid)
    portfolio = app.client.get_portfolio(aid)
    summary = BalanceService.build_summary(positions, portfolio)

    top = ttk.Frame(app.content)
    top.pack(fill="x", pady=(0, 10))
    ttk.Label(top, text=f"Стоимость портфеля: {_money(_field(portfolio, 'total_amount_portfolio'))} {summary.currency or 'RUB'}").pack(side="left")
    ttk.Label(top, text=f"Баланс: {_money(summary.available)} {summary.currency or 'RUB'}").pack(side="left", padx=25)

    tree = app._tree(
        app.content,
        ("Тикер", "UID", "Количество, шт.", "Заблокировано заявками, шт.", "Цена 1 бумаги", "Стоимость", "Доходность"),
        (100, 330, 130, 190, 140, 150, 140),
    )

    portfolio_positions = _items(portfolio, "positions")
    if not portfolio_positions:
        _console(app, f"[PORTFOLIO] account_id={aid}: API вернул 0 позиций")
        ttk.Label(app.content, text="Ценных бумаг в портфеле нет.").pack(anchor="w", pady=12)
        return

    for position in portfolio_positions:
        quantity = _decimal(_field(position, "quantity"))
        price = _decimal(_field(position, "current_price"))
        blocked = _decimal(_field(position, "blocked_lots"))
        value = quantity * price
        yield_value = _decimal(_field(position, "expected_yield"))
        tree.insert(
            "",
            "end",
            values=(
                _text(_field(position, "ticker", "")),
                _text(_field(position, "instrument_uid", _field(position, "figi", ""))),
                f"{quantity:,.0f}".replace(",", " "),
                f"{blocked:,.0f}".replace(",", " "),
                _money(price),
                _money(value),
                f"{yield_value}%",
            ),
        )

    _console(app, f"[PORTFOLIO] account_id={aid} positions={len(portfolio_positions)} portfolio={_field(portfolio, 'total_amount_portfolio')}")


def _page_order(app: Any) -> None:
    ttk.Label(app.content, text="Новая торговая заявка", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
    aid = app._require_account()
    if not aid:
        return
    ins = app.selected_instrument or {}
    uid = str(ins.get("instrument_uid", ""))
    if not uid:
        raise ValueError("Не выбран инструмент")

    status = app.client.get_trading_status(uid)
    api_trade_available = bool(_field(status, "api_trade_available_flag", False))
    market_available = bool(_field(status, "market_order_available_flag", False))
    limit_available = bool(_field(status, "limit_order_available_flag", False))
    available_types = []
    if market_available and api_trade_available:
        available_types.append("Рыночная")
    if limit_available and api_trade_available:
        available_types.append("Лимитная")
    if not available_types:
        raise ValueError(
            "Для выбранного инструмента сейчас нет доступных типов заявок. "
            f"api={api_trade_available}, market={market_available}, limit={limit_available}"
        )

    lot_size = _lot_size(app.client, uid)
    instrument_price = _load_current_price(app.client, uid, ins)
    lot_price = instrument_price * lot_size if instrument_price > 0 else Decimal("0")

    frame = ttk.Frame(app.content)
    frame.pack(fill="x")
    vars: dict[str, Any] = {}
    default_type = "Лимитная" if "Лимитная" in available_types else available_types[0]
    price_default = str(instrument_price) if instrument_price > 0 else ""
    fields = [
        ("ticker", "Инструмент", ins.get("ticker", "")),
        ("side", "Операция", "Покупка"),
        ("order_type", "Тип заявки", default_type),
        ("quantity", "Количество лотов", "1"),
        ("price", "Цена 1 бумаги", price_default),
    ]
    for r, (key, label, default) in enumerate(fields):
        ttk.Label(frame, text=label, width=24).grid(row=r, column=0, sticky="w", pady=5)
        vars[key] = __import__("tkinter").StringVar(value=default)
        if key == "side":
            widget = ttk.Combobox(frame, textvariable=vars[key], state="readonly", values=["Покупка", "Продажа"], width=37)
        elif key == "order_type":
            widget = ttk.Combobox(frame, textvariable=vars[key], state="readonly", values=available_types, width=37)
        elif key == "ticker":
            widget = ttk.Entry(frame, textvariable=vars[key], state="readonly", width=40)
        else:
            widget = ttk.Entry(frame, textvariable=vars[key], width=40)
        widget.grid(row=r, column=1, sticky="w")

    price_text = f"{_money(instrument_price)}" if instrument_price > 0 else "недоступна"
    lot_text = f"{_money(lot_price)}" if lot_price > 0 else "недоступна"
    info = (
        f"Цена 1 бумаги: {price_text} | "
        f"Лотность: {lot_size:,.0f} шт. | "
        f"Цена 1 лота: {lot_text} | "
        f"Текущий торговый статус: {_text(_field(status, 'trading_status', ''))}"
    )
    ttk.Label(app.content, text=info).pack(anchor="w", pady=(12, 4))
    if default_type == "Лимитная" and instrument_price <= 0:
        ttk.Label(app.content, text="Текущая цена недоступна. Для лимитной заявки введите цену вручную.").pack(anchor="w", pady=(0, 12))
    else:
        ttk.Label(app.content, text="").pack(anchor="w", pady=(0, 12))
    ttk.Button(app.content, text="Проверить и подтвердить", command=lambda: _submit(app, vars, lot_size)).pack(anchor="w")
    _console(app, f"[ORDER FORM] account_id={aid} ticker={ins.get('ticker', '')} lot_size={lot_size} price_per_share={instrument_price} price_per_lot={lot_price} price_source={'selected_instrument' if _decimal(ins.get('last_price')) > 0 else 'last_prices_or_unavailable'}")


def _submit(app: Any, variables: dict[str, Any], lot_size: Decimal) -> None:
    aid = app._require_account()
    ins = app.selected_instrument
    if not aid or not ins:
        return
    ticker = str(ins.get("ticker", ""))
    name = str(ins.get("name", ""))
    request: OrderRequest | None = None
    ctx = None
    try:
        quantity = int(variables["quantity"].get())
        if quantity <= 0:
            raise ValueError("Количество лотов должно быть больше нуля.")
        side = OrderSide.BUY if variables["side"].get() == "Покупка" else OrderSide.SELL
        order_type = OrderType.MARKET if variables["order_type"].get() == "Рыночная" else OrderType.LIMIT
        raw_price = variables["price"].get().strip()
        if order_type == OrderType.LIMIT:
            if not raw_price:
                raise ValueError("Для лимитной заявки необходимо указать цену.")
            try:
                price = Decimal(raw_price.replace(",", "."))
            except Exception as exc:
                raise ValueError(f"Некорректная цена: {raw_price!r}") from exc
            if price <= 0:
                raise ValueError("Цена должна быть больше нуля.")
        else:
            price = None
        request = OrderRequest(
            account_id=aid,
            instrument_uid=str(ins["instrument_uid"]),
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            instrument_kind=str(ins.get("instrument_kind", "SHARE")),
        )
        _console(app, f"[ORDER VALIDATION] {side.value} {ticker} quantity_lots={quantity} price_per_share={price}")
        ctx = TradingValidator(AdapterTradingDataProvider(app.client)).validate(request)
    except Exception as exc:
        _console(app, f"[ORDER FAILED] {ticker} проверка отклонена: {type(exc).__name__}: {exc}")
        if request is not None:
            _append_history_error(app, request, ticker, name, exc, request.price, getattr(ctx, "estimated_total", None) if ctx else None)
        app._show_error(exc, "проверка заявки")
        return

    total = ctx.estimated_total or Decimal("0")
    commission = ctx.estimated_commission or Decimal("0")
    price_one = price or ctx.market_price
    if order_type == OrderType.LIMIT and (price_one is None or price_one <= 0):
        app._show_error(ValueError("Не удалось определить цену лимитной заявки."), "проверка заявки")
        return
    price_one = price_one or Decimal("0")
    lot_price = price_one * lot_size if price_one > 0 else Decimal("0")
    confirmation = (
        f"Инструмент: {ticker}\n"
        f"Операция: {side.value}\n"
        f"Количество: {quantity} лот(ов) = {quantity * lot_size:,.0f} шт.\n"
        f"Цена 1 бумаги: {_money(price_one)}\n"
        f"Цена 1 лота: {_money(lot_price)}\n"
        f"Комиссия: {_money(commission)}\n"
        f"Итого: {_money(total + commission)}\n\n"
        "Отправить заявку?"
    )
    if not messagebox.askyesno("Подтверждение заявки", confirmation):
        _console(app, f"[ORDER CANCELLED] {ticker} {side.value} пользователь отменил подтверждение")
        return

    try:
        _console(app, f"[ORDER SEND] {ticker} {side.value} quantity_lots={quantity} account_id={aid}")
        result = OrderService(app.client).create_order(request)
        oid = str(_field(result, "order_id", ""))
        app.tracked_orders[oid] = {
            "account_id": aid,
            "instrument_uid": request.instrument_uid,
            "ticker": ticker,
            "name": name,
            "operation": side.value,
            "quantity": quantity,
            "order_type": order_type.value,
            "currency": ins.get("currency", "RUB"),
        }
        _console(app, f"[ORDER SUCCESS] {ticker} {side.value} order_id={oid} status=SUBMITTED")
        app.show_page("orders")
    except Exception as exc:
        _console(app, f"[ORDER FAILED] {ticker} отправка: {type(exc).__name__}: {exc}")
        _append_history_error(app, request, ticker, name, exc, price_one, total + commission)
        app._show_error(exc, "создание заявки")


def _poll_orders(app: Any) -> None:
    for oid, meta in list(app.tracked_orders.items()):
        try:
            state = app.client.get_order_state(meta["account_id"], oid)
            raw_status = _field(state, "execution_report_status", _field(state, "status", ""))
            status = str(raw_status).upper()
            executed = int(_decimal(_field(state, "lots_executed", _field(state, "quantity_executed", 0))))
            if "FILL" in status and "PART" not in status:
                record = TradeRecord(
                    account_id=meta["account_id"], order_id=oid, instrument_uid=meta["instrument_uid"],
                    operation=meta["operation"], quantity=executed or int(meta["quantity"]), order_type=meta["order_type"],
                    execution_price=_decimal(_field(state, "executed_order_price", _field(state, "initial_security_price", None))),
                    amount=_decimal(_field(state, "total_order_amount", None)), commission=_decimal(_field(state, "executed_commission", None)),
                    currency=str(_field(state, "currency", meta.get("currency", "RUB"))), status="FILLED", figi=str(_field(state, "figi", "")),
                    ticker=meta["ticker"], name=meta["name"],
                )
                app.history.save_completed(record)
                app.tracked_orders.pop(oid, None)
                _console(app, f"[ORDER FILLED] order_id={oid} ticker={meta['ticker']} quantity_lots={record.quantity}")
            elif any(token in status for token in ("REJECT", "CANCEL", "FAIL", "ERROR")):
                record = TradeRecord(
                    account_id=meta["account_id"], order_id=oid, instrument_uid=meta["instrument_uid"], operation=meta["operation"],
                    quantity=int(meta["quantity"]), order_type=meta["order_type"], execution_price=None, amount=None, commission=Decimal("0"),
                    currency=str(meta.get("currency", "RUB")), status="ERROR", ticker=meta["ticker"], name=meta["name"],
                )
                app.history.save(record)
                app.tracked_orders.pop(oid, None)
                _console(app, f"[ORDER FAILED] order_id={oid} ticker={meta['ticker']} status={status}")
            else:
                _console(app, f"[ORDER STATUS] order_id={oid} ticker={meta['ticker']} status={status} executed={executed}/{meta['quantity']}")
        except Exception as exc:
            _console(app, f"[POLL ERROR] order_id={oid}: {type(exc).__name__}: {exc}")


def _show_error(app: Any, exc: Exception, context: str = "") -> None:
    _console(app, f"[ERROR] context={context} type={type(exc).__name__}: {exc}")
    detail = f"Edward Trading Platform v0.1\nКонтекст: {context}\nОшибка: {type(exc).__name__}: {exc}"
    import tkinter as tk
    d = tk.Toplevel(app)
    d.title("Ошибка Edward")
    d.geometry("900x520")
    t = tk.Text(d, wrap="word")
    t.pack(fill="both", expand=True, padx=10, pady=10)
    t.insert("1.0", detail)
    t.configure(state="disabled")
    b = ttk.Frame(d)
    b.pack(fill="x", padx=10, pady=10)
    ttk.Button(b, text="Скопировать", command=lambda: (app.clipboard_clear(), app.clipboard_append(detail), app.update())).pack(side="left")
    ttk.Button(b, text="Закрыть", command=d.destroy).pack(side="right")


def install_ux_fixes(EdwardApp: Any) -> None:
    if getattr(EdwardApp, _SENTINEL, False):
        return
    EdwardApp._page_overview = _page_overview
    EdwardApp._page_portfolio = _page_portfolio
    EdwardApp._page_order = _page_order
    EdwardApp._submit = lambda self, variables: _submit(self, variables, _lot_size(self.client, str(self.selected_instrument.get("instrument_uid", ""))) if self.selected_instrument else Decimal("1"))
    EdwardApp._poll_orders = _poll_orders
    EdwardApp._show_error = _show_error

    original_show_page = EdwardApp.show_page
    def logged_show_page(self: Any, page: str) -> None:
        _console(self, f"[UI] Открыта вкладка: {page}")
        original_show_page(self, page)
    EdwardApp.show_page = logged_show_page

    original_refresh = EdwardApp.refresh_current
    def logged_refresh(self: Any) -> None:
        _console(self, f"[UI] Обновление: {self.current_page}")
        try:
            original_refresh(self)
            _console(self, f"[UI SUCCESS] Обновлено: {self.current_page}")
        except Exception as exc:
            _console(self, f"[UI FAILED] Обновление {self.current_page}: {type(exc).__name__}: {exc}")
            raise
    EdwardApp.refresh_current = logged_refresh

    setattr(EdwardApp, _SENTINEL, True)
