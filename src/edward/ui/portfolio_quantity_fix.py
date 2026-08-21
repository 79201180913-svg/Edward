from __future__ import annotations

from decimal import Decimal
from tkinter import ttk
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


def _money(value: Any) -> str:
    return f"{_decimal(value):,.2f}".replace(",", " ")


def _uid(value: Any) -> str:
    return str(_field(value, "instrument_uid", _field(value, "uid", "")) or "")


def _is_cash_position(position: Any) -> bool:
    ticker = str(_field(position, "ticker", "") or "").upper()
    currency = str(_field(position, "currency", "") or "").upper()
    instrument_type = str(_field(position, "instrument_type", _field(position, "instrument_kind", "")) or "").upper()
    return (
        ticker == "RUB000UTSTOM"
        or ticker.startswith("RUB")
        or (currency == "RUB" and instrument_type in {"CURRENCY", "INSTRUMENT_TYPE_CURRENCY"})
    )


def _find_security(position: Any, securities: list[Any]) -> Any:
    keys = {
        str(_field(position, "instrument_uid", "") or ""),
        str(_field(position, "position_uid", "") or ""),
        str(_field(position, "figi", "") or ""),
        str(_field(position, "ticker", "") or ""),
    }
    keys.discard("")
    for item in securities:
        item_keys = {
            str(_field(item, "instrument_uid", "") or ""),
            str(_field(item, "position_uid", "") or ""),
            str(_field(item, "figi", "") or ""),
            str(_field(item, "ticker", "") or ""),
        }
        if keys & item_keys:
            return item
    return None


def _lot_size(client: Any, uid: str) -> Decimal:
    if not uid:
        return Decimal("1")
    try:
        instrument = client.get_instrument(uid)
        for name in ("lot", "lot_size"):
            value = _decimal(_field(instrument, name, 0))
            if value > 0:
                return value
    except Exception:
        pass
    return Decimal("1")


def _operation_direction(operation: Any) -> str:
    raw = _field(operation, "operation_type", _field(operation, "type", ""))
    text = str(raw).upper()
    if "BUY" in text or "ПОКУП" in text:
        return "BUY"
    if "SELL" in text or "ПРОДАЖ" in text:
        return "SELL"
    try:
        number = int(raw)
    except Exception:
        return ""
    return {15: "BUY", 16: "BUY", 22: "SELL"}.get(number, "")


def _operation_executed(operation: Any) -> bool:
    raw = _field(operation, "state", _field(operation, "status", ""))
    text = str(raw).upper()
    if any(token in text for token in ("CANCEL", "REJECT", "FAIL", "ERROR")):
        return False
    if any(token in text for token in ("EXECUT", "FILL", "SUCCESS")):
        return True
    try:
        return int(raw) == 1
    except Exception:
        return raw in ("", None)


def _operations_quantity(client: Any, account_id: str) -> dict[str, Decimal]:
    try:
        response = client.get_operations(account_id, 1000)
    except Exception as exc:
        print(f"[PORTFOLIO OPERATIONS ERROR] {type(exc).__name__}: {exc}", flush=True)
        return {}

    totals: dict[str, Decimal] = {}
    operations = _items(response, "operations", "items")
    for operation in operations:
        if not _operation_executed(operation):
            continue
        direction = _operation_direction(operation)
        if direction not in {"BUY", "SELL"}:
            continue
        keys = (
            _field(operation, "instrument_uid", ""),
            _field(operation, "position_uid", ""),
            _field(operation, "figi", ""),
            _field(operation, "ticker", ""),
        )
        key = next((str(value) for value in keys if value), "")
        if not key:
            continue
        quantity = _decimal(_field(operation, "quantity_done", _field(operation, "quantity", 0)))
        if quantity <= 0:
            continue
        sign = Decimal("1") if direction == "BUY" else Decimal("-1")
        totals[key] = totals.get(key, Decimal("0")) + sign * quantity

    print(f"[PORTFOLIO OPERATIONS QUANTITY] account_id={account_id} instruments={len(totals)} totals={totals}", flush=True)
    return totals


def _quantity(client: Any, position: Any, security: Any, operation_totals: dict[str, Decimal]) -> tuple[Decimal, Decimal, str]:
    quantity = _decimal(_field(position, "quantity", 0))
    blocked = _decimal(_field(position, "blocked_lots", 0))
    if quantity > 0:
        if blocked <= 0 and security is not None:
            blocked = _decimal(_field(security, "blocked", 0))
        return quantity, blocked, "PortfolioPosition.quantity"

    quantity_lots = _decimal(_field(position, "quantity_lots", 0))
    uid = _uid(position)
    if quantity_lots > 0:
        lot_size = _lot_size(client, uid)
        blocked_value = blocked
        if blocked_value <= 0 and security is not None:
            blocked_value = _decimal(_field(security, "blocked", 0))
        return quantity_lots * lot_size, blocked_value, f"PortfolioPosition.quantity_lots*lot({lot_size})"

    keys = (
        _field(position, "instrument_uid", ""),
        _field(position, "position_uid", ""),
        _field(position, "figi", ""),
        _field(position, "ticker", ""),
    )
    for key in keys:
        text = str(key or "")
        if text in operation_totals and operation_totals[text] > 0:
            return operation_totals[text], blocked, "GetSandboxOperationsByCursor BUY-SELL"

    balance = _decimal(_field(security, "balance", 0)) if security is not None else Decimal("0")
    security_blocked = _decimal(_field(security, "blocked", 0)) if security is not None else Decimal("0")
    return balance + security_blocked, security_blocked, "PositionsSecurities.balance+blocked"


def install_portfolio_quantity_fix(EdwardApp: Any) -> None:
    def _page_portfolio(self: Any) -> None:
        ttk.Label(self.content, text="Портфель", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        aid = self._require_account()
        if not aid:
            print("[PORTFOLIO] Нет активного счёта", flush=True)
            return

        positions = self.client.get_positions(aid)
        portfolio = self.client.get_portfolio(aid)
        securities = _items(positions, "securities")
        portfolio_positions = _items(portfolio, "positions")
        operation_totals = _operations_quantity(self.client, aid)

        tree = self._tree(
            self.content,
            ("Тикер", "UID", "Количество, шт.", "Заблокировано заявками, шт.", "Цена 1 бумаги", "Стоимость", "Доходность"),
            (110, 340, 140, 210, 140, 150, 140),
        )

        total_value = Decimal("0")
        displayed = 0
        for position in portfolio_positions:
            if _is_cash_position(position):
                print(f"[PORTFOLIO CASH] ticker={_field(position, 'ticker', '')} excluded from securities table", flush=True)
                continue

            security = _find_security(position, securities)
            quantity, blocked, source = _quantity(self.client, position, security, operation_totals)
            uid = str(_field(position, "instrument_uid", _field(position, "uid", _field(security, "instrument_uid", ""))) or "")
            ticker = str(_field(position, "ticker", _field(security, "ticker", "")) or "")
            price = _decimal(_field(position, "current_price", 0))
            if price <= 0 and uid:
                try:
                    response = self.client.get_last_prices([uid])
                    prices = _items(response, "last_prices")
                    if prices:
                        price = _decimal(_field(prices[0], "price", _field(prices[0], "last_price", 0)))
                except Exception as exc:
                    print(f"[PORTFOLIO PRICE ERROR] uid={uid}: {exc}", flush=True)

            value = quantity * price
            total_value += value
            yield_value = _decimal(_field(position, "expected_yield", _field(position, "expected_yield_fifo", 0)))
            tree.insert(
                "", "end",
                values=(
                    ticker,
                    uid,
                    f"{quantity:,.0f}".replace(",", " "),
                    f"{blocked:,.0f}".replace(",", " "),
                    _money(price),
                    _money(value),
                    f"{yield_value}",
                ),
            )
            displayed += 1
            print(
                f"[PORTFOLIO POSITION] ticker={ticker} uid={uid} quantity={quantity} blocked={blocked} source={source} "
                f"raw_quantity={_field(position, 'quantity', None)!r} raw_quantity_lots={_field(position, 'quantity_lots', None)!r} "
                f"security_balance={_field(security, 'balance', None)!r} security_blocked={_field(security, 'blocked', None)!r}",
                flush=True,
            )

        if displayed == 0:
            ttk.Label(self.content, text="Ценных бумаг в портфеле нет.").pack(anchor="w", pady=12)

        print(f"[PORTFOLIO] account_id={aid} displayed={displayed} securities_value={total_value}", flush=True)

    EdwardApp._page_portfolio = _page_portfolio
