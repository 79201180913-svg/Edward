from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from edward.domain.execution import ExecutionDecision, ExecutionRequest

ACTIONABLE = {
    ExecutionDecision.BUY,
    ExecutionDecision.ADD,
    ExecutionDecision.REDUCE,
    ExecutionDecision.SELL,
}


class LivePreTradeValidator:
    """Live broker/account revalidation immediately before order submission."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def validate(self, request: ExecutionRequest) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        decision = request.decision
        if decision not in ACTIONABLE:
            reasons.append("DECISION_NOT_EXECUTABLE")
            return False, tuple(reasons)
        self._check_account(request, reasons)
        instrument = self._get_instrument(request, reasons)
        live_price = self._get_live_price(request, reasons)
        self._check_trading_status(request, reasons)
        self._check_quantity(request, reasons)
        self._check_price(request, instrument, live_price, reasons)
        self._check_position(request, reasons)
        self._check_cash(request, live_price, reasons)
        self._check_max_lots(request, live_price, reasons)
        return not reasons, tuple(reasons)

    def _check_account(self, request: ExecutionRequest, reasons: list[str]) -> None:
        try:
            accounts = _items(self.client.get_accounts(), "accounts")
        except Exception:
            reasons.append("ACCOUNT_NOT_AVAILABLE")
            return
        account = next((item for item in accounts if _id(item) == request.account_id), None)
        if account is None or str(_field(account, "status", "")).upper() in {
            "ACCOUNT_STATUS_CLOSED", "CLOSED", "ACCOUNT_STATUS_BLOCKED", "BLOCKED"
        }:
            reasons.append("ACCOUNT_NOT_AVAILABLE")

    def _get_instrument(self, request: ExecutionRequest, reasons: list[str]) -> Any:
        try:
            return self.client.get_instrument(request.instrument_uid)
        except Exception:
            return None

    def _get_live_price(self, request: ExecutionRequest, reasons: list[str]) -> Decimal | None:
        try:
            payload = self.client.get_last_prices([request.instrument_uid])
            items = _items(payload, "last_prices", "prices")
            item = next(
                (value for value in items if _field(value, "instrument_uid", _field(value, "uid", "")) == request.instrument_uid),
                items[0] if items else None,
            )
            price = _decimal(_field(item, "price", _field(item, "last_price", None))) if item is not None else Decimal("0")
        except Exception:
            price = Decimal("0")
        if price <= 0:
            reasons.append("LIVE_PRICE_UNAVAILABLE")
            return None
        return price

    def _check_trading_status(self, request: ExecutionRequest, reasons: list[str]) -> None:
        try:
            status = self.client.get_trading_status(request.instrument_uid)
        except Exception:
            reasons.append("TRADING_STATUS_NOT_OK")
            return
        available = _bool_field(status, "api_trade_available", None)
        raw = " ".join(str(_field(status, name, "")) for name in ("status", "trading_status", "execution_report_status")).upper()
        unavailable_marker = any(token in raw for token in ("NOT_AVAILABLE", "CLOSED", "HALTED", "SUSPEND"))
        order_available = any(_bool_field(status, name, False) for name in ("limit_order_available", "market_order_available", "bestprice_order_available"))
        if available is False or unavailable_marker or (available is None and not order_available):
            reasons.append("TRADING_STATUS_NOT_OK")

    def _check_quantity(self, request: ExecutionRequest, reasons: list[str]) -> None:
        if request.quantity <= 0:
            reasons.append("INVALID_QUANTITY")

    def _check_price(self, request: ExecutionRequest, instrument: Any, live_price: Decimal | None, reasons: list[str]) -> None:
        price = request.entry_price if request.order_type.lower() == "limit" else live_price
        if request.order_type.lower() == "limit" and (price is None or price <= 0):
            reasons.append("ENTRY_PRICE_REQUIRED")
            return
        increment = _decimal(_field(instrument, "min_price_increment", None)) if instrument is not None else Decimal("0")
        if price is not None and increment > 0 and (price / increment) != (price / increment).to_integral_value():
            reasons.append("INVALID_PRICE_STEP")

    def _check_position(self, request: ExecutionRequest, reasons: list[str]) -> None:
        if request.decision not in {ExecutionDecision.REDUCE, ExecutionDecision.SELL}:
            return
        try:
            payload = self.client.get_positions(request.account_id)
            positions = _items(payload, "securities", "positions")
        except Exception:
            reasons.append("POSITION_NOT_AVAILABLE")
            return
        position = next((item for item in positions if _field(item, "instrument_uid", _field(item, "uid", "")) == request.instrument_uid), None)
        quantity = _decimal(_field(position, "balance", _field(position, "quantity", 0))) if position is not None else Decimal("0")
        if quantity < request.quantity:
            reasons.append("INSUFFICIENT_POSITION")

    def _check_cash(self, request: ExecutionRequest, live_price: Decimal | None, reasons: list[str]) -> None:
        if request.decision not in {ExecutionDecision.BUY, ExecutionDecision.ADD} or live_price is None:
            return
        try:
            payload = self.client.get_portfolio(request.account_id)
            available_cash = _available_cash(payload)
        except Exception:
            reasons.append("CASH_NOT_AVAILABLE")
            return
        if available_cash is not None and available_cash < live_price * request.quantity:
            reasons.append("INSUFFICIENT_CASH")

    def _check_max_lots(self, request: ExecutionRequest, live_price: Decimal | None, reasons: list[str]) -> None:
        # Entry-side broker limit only. REDUCE/SELL are constrained by the held
        # position, which is checked separately above. Do not call /orders/max-lots
        # for exits because the sandbox adapter may legitimately return not_found.
        if request.decision not in {ExecutionDecision.BUY, ExecutionDecision.ADD}:
            return
        if live_price is None or request.quantity <= 0:
            return
        try:
            payload = self.client.get_max_lots(request.account_id, request.instrument_uid, live_price)
            max_lots = _decimal(_field(payload, "max_lots", _field(payload, "lots", _field(payload, "quantity", 0))))
        except Exception:
            reasons.append("MAX_LOTS_CHECK_FAILED")
            return
        if max_lots < request.quantity:
            reasons.append("INSUFFICIENT_MAX_LOTS")


def _field(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _id(value: Any) -> str:
    return str(_field(value, "id", _field(value, "account_id", "")) or "")


def _items(value: Any, *names: str) -> list[Any]:
    if isinstance(value, list):
        return value
    for name in names:
        items = _field(value, name, None)
        if items is not None:
            return list(items)
    return []


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Mapping) and ("units" in value or "nano" in value):
        try:
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        except Exception:
            return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _bool_field(value: Any, name: str, default: bool | None) -> bool | None:
    raw = _field(value, name, default)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "да"}


def _available_cash(payload: Any) -> Decimal | None:
    direct = _field(payload, "available_cash", None)
    if direct is not None:
        return _decimal(direct)
    money = _items(payload, "money")
    for item in money:
        currency = str(_field(item, "currency", "")).upper()
        if currency in {"RUB", "USD"}:
            value = _field(item, "available", _field(item, "available_value", None))
            return _decimal(value)
    return None


__all__ = ["LivePreTradeValidator"]
