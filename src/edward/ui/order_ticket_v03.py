from __future__ import annotations

import tkinter as tk
from decimal import Decimal
from typing import Any
from tkinter import messagebox, ttk

from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.validation.trading_validator import TradingValidator, ValidationContext


_LABEL_TO_TYPE = {
    "Рыночная": OrderType.MARKET,
    "Лимитная": OrderType.LIMIT,
    "Лучшая цена": OrderType.BESTPRICE,
}


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _money(value: Decimal, currency: str) -> str:
    return f"{value:,.2f}".replace(",", " ") + (f" {currency}" if currency else "")


def install_order_ticket(app_class: type[Any]) -> None:
    if getattr(app_class, "_order_ticket_v03_installed", False):
        return

    def page_order(self: Any) -> None:
        ttk.Label(self.content, text="Новая торговая заявка", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        account_id = self._require_account()
        if not account_id:
            return

        instrument = self.selected_instrument or {}
        uid = str(instrument.get("instrument_uid", instrument.get("uid", "")))
        if not uid:
            ttk.Label(self.content, text="Сначала выберите инструмент.").pack(anchor="w")
            return

        status = self.client.get_trading_status(uid)
        api_trade_available = bool(_field(status, "api_trade_available_flag", False))
        buy_available = bool(_field(status, "buy_available_flag", instrument.get("buy_available", False)))
        sell_available = bool(_field(status, "sell_available_flag", instrument.get("sell_available", False)))
        market_available = bool(_field(status, "market_order_available_flag", False))
        limit_available = bool(_field(status, "limit_order_available_flag", False))
        bestprice_available = bool(_field(status, "bestprice_order_available_flag", False))

        available_types: list[str] = []
        if limit_available and api_trade_available:
            available_types.append("Лимитная")
        if market_available and api_trade_available:
            available_types.append("Рыночная")
        if bestprice_available and api_trade_available:
            available_types.append("Лучшая цена")
        if not available_types:
            raise ValueError("Для выбранного инструмента сейчас нет доступных типов заявок.")

        sides: list[str] = []
        if buy_available:
            sides.append("Покупка")
        if sell_available:
            sides.append("Продажа")
        if not sides:
            raise ValueError("Покупка и продажа сейчас недоступны для выбранного инструмента.")

        default_type = "Лимитная" if "Лимитная" in available_types else available_types[0]
        default_side = "Покупка" if "Покупка" in sides else sides[0]
        currency = str(instrument.get("currency") or "RUB").upper()
        current_price = _decimal(instrument.get("last_price"))
        if current_price <= 0:
            try:
                prices = self.client.get_last_prices([uid])
                items = self._items(prices, "last_prices")
                if items:
                    current_price = _decimal(_field(items[0], "price"))
            except Exception:
                pass
        increment = _decimal(instrument.get("min_price_increment"))

        shell = ttk.LabelFrame(self.content, text=f"{instrument.get('ticker', '')} — {instrument.get('name', '')}", padding=12)
        shell.pack(fill="x")

        vars_: dict[str, tk.StringVar] = {
            "side": tk.StringVar(value=default_side),
            "type": tk.StringVar(value=default_type),
            "quantity": tk.StringVar(value="1"),
            "price": tk.StringVar(value=str(current_price) if current_price > 0 else ""),
            "summary": tk.StringVar(value="Проверьте заявку перед отправкой."),
        }
        widgets: dict[str, Any] = {}

        def add_row(row: int, label: str, key: str, widget: Any) -> None:
            ttk.Label(shell, text=label, width=24).grid(row=row, column=0, sticky="w", pady=5)
            widget.grid(row=row, column=1, sticky="w", pady=5)
            widgets[key] = widget

        add_row(0, "Инструмент", "instrument", ttk.Label(shell, text=f"{instrument.get('ticker', '')}  {instrument.get('name', '')}"))
        add_row(1, "Операция", "side", ttk.Combobox(shell, textvariable=vars_["side"], values=sides, state="readonly", width=38))
        add_row(2, "Тип заявки", "type", ttk.Combobox(shell, textvariable=vars_["type"], values=available_types, state="readonly", width=38))
        add_row(3, "Количество лотов", "quantity", ttk.Entry(shell, textvariable=vars_["quantity"], width=40))
        add_row(4, "Цена за 1 шт.", "price", ttk.Entry(shell, textvariable=vars_["price"], width=40))

        info = ttk.Frame(shell)
        info.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 2))
        ttk.Label(info, text=f"Текущая цена: {_money(current_price, currency) if current_price > 0 else 'недоступна'}").pack(side="left")
        ttk.Label(info, text=f"  |  Шаг цены: {_money(increment, currency) if increment > 0 else 'неизвестен'}").pack(side="left")

        summary = ttk.LabelFrame(self.content, text="Предпросмотр заявки", padding=12)
        summary.pack(fill="x", pady=(12, 0))
        ttk.Label(summary, textvariable=vars_["summary"], justify="left").pack(anchor="w")

        actions = ttk.Frame(self.content)
        actions.pack(fill="x", pady=12)
        check_button = ttk.Button(actions, text="Проверить заявку")
        send_button = ttk.Button(actions, text="Отправить заявку", state="disabled")
        check_button.pack(side="left")
        send_button.pack(side="left", padx=8)

        state: dict[str, Any] = {"request": None, "context": None}

        def refresh_price_state(*_: Any) -> None:
            limit = vars_["type"].get() == "Лимитная"
            widgets["price"].configure(state="normal" if limit else "disabled")
            if not limit:
                widgets["price"].delete(0, "end")
            elif not vars_["price"].get() and current_price > 0:
                widgets["price"].insert(0, str(current_price))
            state["request"] = None
            state["context"] = None
            send_button.configure(state="disabled")
            vars_["summary"].set("Параметры изменены. Нажмите «Проверить заявку»." )

        vars_["type"].trace_add("write", refresh_price_state)
        vars_["side"].trace_add("write", refresh_price_state)
        refresh_price_state()

        def build_request() -> OrderRequest:
            try:
                quantity = int(vars_["quantity"].get().strip())
            except ValueError as exc:
                raise ValueError("Количество лотов должно быть целым числом.") from exc
            if quantity <= 0:
                raise ValueError("Количество лотов должно быть больше нуля.")
            side = OrderSide.BUY if vars_["side"].get() == "Покупка" else OrderSide.SELL
            order_type = _LABEL_TO_TYPE[vars_["type"].get()]
            price: Decimal | None = None
            if order_type is OrderType.LIMIT:
                raw = vars_["price"].get().strip().replace(",", ".")
                if not raw:
                    raise ValueError("Для лимитной заявки необходимо указать цену.")
                try:
                    price = Decimal(raw)
                except Exception as exc:
                    raise ValueError("Цена должна быть числом.") from exc
                if price <= 0:
                    raise ValueError("Цена должна быть больше нуля.")
            return OrderRequest(
                account_id=account_id,
                instrument_uid=uid,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                instrument_kind=str(instrument.get("instrument_kind", "SHARE")),
            )

        def check() -> None:
            try:
                request = build_request()
                context: ValidationContext = TradingValidator(AdapterTradingDataProvider(self.client)).validate(request)
                market = context.market_price or current_price
                total = context.estimated_total or Decimal("0")
                commission = context.estimated_commission or Decimal("0")
                display_price = request.price if request.price is not None else market
                available_money = context.available_money
                available_position = context.available_position
                lines = [
                    f"{instrument.get('ticker', '')}  |  {request.side.value}  |  {request.order_type.value}",
                    f"Количество: {request.quantity} лот(ов)",
                    f"Цена: {_money(display_price, currency) if display_price else 'по рынку'}",
                    f"Оценка сделки: {_money(total, currency)}",
                    f"Комиссия: {_money(commission, currency)}",
                ]
                if available_money is not None:
                    lines.append(f"Доступно средств: {_money(available_money, currency)}")
                if available_position is not None:
                    lines.append(f"Доступно к продаже: {available_position} лот(ов)")
                vars_["summary"].set("\n".join(lines) + "\n\nПроверка пройдена. Можно отправлять заявку.")
                state["request"] = request
                state["context"] = context
                send_button.configure(state="normal")
            except Exception as exc:
                state["request"] = None
                state["context"] = None
                send_button.configure(state="disabled")
                messagebox.showerror("Проверка заявки", str(exc), parent=self)

        def send() -> None:
            request = state.get("request")
            context = state.get("context")
            if request is None or context is None:
                messagebox.showwarning("Заявка", "Сначала выполните проверку заявки.", parent=self)
                return
            total = context.estimated_total or Decimal("0")
            commission = context.estimated_commission or Decimal("0")
            display_price = request.price if request.price is not None else (context.market_price or current_price)
            confirm = messagebox.askyesno(
                "Подтверждение заявки",
                f"Инструмент: {instrument.get('ticker', '')}\n"
                f"Операция: {request.side.value}\n"
                f"Тип: {request.order_type.value}\n"
                f"Количество: {request.quantity}\n"
                f"Цена: {_money(display_price, currency) if display_price else 'по рынку'}\n"
                f"Комиссия: {_money(commission, currency)}\n"
                f"Итого: {_money(total + commission, currency)}\n\n"
                "Отправить заявку?",
                parent=self,
            )
            if not confirm:
                return
            try:
                result = OrderService(self.client).create_order(request)
                order_id = str(_field(result, "order_id", ""))
                self.tracked_orders[order_id] = {
                    "account_id": account_id,
                    "instrument_uid": request.instrument_uid,
                    "ticker": instrument.get("ticker", ""),
                    "name": instrument.get("name", ""),
                    "operation": request.side.value,
                    "quantity": request.quantity,
                    "order_type": request.order_type.value,
                    "currency": currency,
                }
                messagebox.showinfo("Заявка отправлена", f"Заявка создана.\nID: {order_id}", parent=self)
                self.show_page("orders")
            except Exception as exc:
                messagebox.showerror("Создание заявки", str(exc), parent=self)

        check_button.configure(command=check)
        send_button.configure(command=send)

    app_class._page_order = page_order
    app_class._order_ticket_v03_installed = True
