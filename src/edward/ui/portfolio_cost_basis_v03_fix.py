from __future__ import annotations

from decimal import Decimal
from typing import Any


def field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict):
        if "units" in value or "nano" in value:
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        for key in ("value", "amount", "price", "payment"):
            if key in value:
                return decimal(value[key])
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _items(value: Any, *names: str) -> list[Any]:
    if isinstance(value, list):
        return value
    for name in names:
        item = field(value, name, None)
        if item is not None:
            return list(item or [])
    return []


def _operation_kind(operation: Any) -> str:
    raw = field(operation, "type", field(operation, "operation_type", field(operation, "operationType", "")))
    if isinstance(raw, int):
        return {15: "BUY", 16: "BUY", 22: "SELL"}.get(raw, "OTHER")
    text = str(raw).upper()
    if "BUY" in text:
        return "BUY"
    if "SELL" in text:
        return "SELL"
    return "OTHER"


def _aliases(operation: Any) -> list[str]:
    result: list[str] = []
    candidates = [
        operation,
        field(operation, "instrument", None),
        field(operation, "instrument_info", None),
        field(operation, "instrumentInfo", None),
        field(operation, "position", None),
    ]
    names = (
        "instrument_uid", "instrumentUid", "instrument_id", "instrumentId",
        "uid", "position_uid", "positionUid", "figi", "ticker",
    )
    for candidate in candidates:
        if candidate is None:
            continue
        for name in names:
            value = field(candidate, name, None)
            if value not in (None, ""):
                text = str(value)
                if text and text not in result:
                    result.append(text)
    return result


def _trades(operation: Any) -> list[Any]:
    direct = _items(operation, "trades", "trade_items", "tradeItems")
    if direct:
        return direct
    trades_info = field(operation, "trades_info", field(operation, "tradesInfo", None))
    return _items(trades_info, "trades", "trade_items", "tradeItems")


def _trade_quantity(trade: Any) -> Decimal:
    for name in ("quantity", "quantity_lots", "quantityLots", "lots"):
        value = field(trade, name, None)
        if value is not None:
            result = abs(decimal(value))
            if result:
                return result
    return Decimal("0")


def _trade_price(trade: Any) -> Decimal:
    for name in ("price", "trade_price", "tradePrice"):
        value = field(trade, name, None)
        if value is not None:
            result = abs(decimal(value))
            if result:
                return result
    return Decimal("0")


def _quantity(operation: Any) -> Decimal:
    for name in ("quantity_done", "quantityDone", "quantity", "executed_lots", "executedLots", "lots"):
        value = field(operation, name, None)
        if value is not None:
            result = abs(decimal(value))
            if result:
                return result
    return sum((_trade_quantity(t) for t in _trades(operation)), Decimal("0"))


def _payment(operation: Any) -> Decimal:
    for name in ("payment", "amount", "sum"):
        value = field(operation, name, None)
        if value is not None:
            result = abs(decimal(value))
            if result:
                return result
    total = Decimal("0")
    for trade in _trades(operation):
        payment = field(trade, "payment", field(trade, "amount", field(trade, "sum", None)))
        if payment is not None:
            value = abs(decimal(payment))
            if value:
                total += value
                continue
        quantity = _trade_quantity(trade)
        price = _trade_price(trade)
        if quantity and price:
            total += quantity * price
    return total


def _sort_key(operation: Any) -> str:
    return str(field(operation, "date", field(operation, "timestamp", field(operation, "execution_time", field(operation, "executionTime", "")))) or "")


def _safe_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(str(k) for k in value.keys())
    keys: list[str] = []
    try:
        for name in ("type", "operation_type", "quantity", "quantity_done", "payment", "instrument_uid", "figi", "ticker", "trades_info", "trades"):
            if hasattr(value, name):
                keys.append(name)
    except Exception:
        pass
    return sorted(keys)


def robust_build_cost_basis(operations: list[Any]) -> dict[str, dict[str, Decimal]]:
    state: dict[str, dict[str, Decimal]] = {}
    aliases: dict[str, str] = {}
    stats = {
        "total": len(operations),
        "buy": 0,
        "sell": 0,
        "other": 0,
        "with_aliases": 0,
        "with_quantity": 0,
        "with_payment": 0,
        "with_trades": 0,
        "accepted": 0,
    }

    for index, operation in enumerate(sorted(operations, key=_sort_key)):
        kind = _operation_kind(operation)
        if kind == "BUY":
            stats["buy"] += 1
        elif kind == "SELL":
            stats["sell"] += 1
        else:
            stats["other"] += 1
        names = _aliases(operation)
        quantity = _quantity(operation)
        payment = _payment(operation)
        trades = _trades(operation)
        if names:
            stats["with_aliases"] += 1
        if quantity > 0:
            stats["with_quantity"] += 1
        if payment > 0:
            stats["with_payment"] += 1
        if trades:
            stats["with_trades"] += 1

        if index < 3:
            print(
                f"[PORTFOLIO COST BASIS DIAG] op={index + 1} kind={kind} "
                f"keys={_safe_keys(operation)} aliases={bool(names)} "
                f"quantity={quantity > 0} payment={payment > 0} trades={len(trades)}",
                flush=True,
            )

        if kind not in {"BUY", "SELL"} or not names or quantity <= 0 or payment <= 0:
            continue

        stats["accepted"] += 1
        canonical = aliases.get(names[0], names[0])
        for alias in names:
            aliases.setdefault(alias, canonical)

        entry = state.setdefault(canonical, {"quantity": Decimal("0"), "cost": Decimal("0")})
        if kind == "BUY":
            entry["quantity"] += quantity
            entry["cost"] += payment
        elif entry["quantity"] > 0:
            average = entry["cost"] / entry["quantity"]
            sold = min(quantity, entry["quantity"])
            entry["quantity"] -= sold
            entry["cost"] -= average * sold

    print(f"[PORTFOLIO COST BASIS DIAG] stats={stats}", flush=True)

    result: dict[str, dict[str, Decimal]] = {}
    for canonical, value in state.items():
        if value["quantity"] <= 0:
            continue
        result[canonical] = {
            "quantity": value["quantity"],
            "cost": value["cost"],
            "average_price": value["cost"] / value["quantity"],
        }

    for alias, canonical in aliases.items():
        if canonical in result:
            result[alias] = result[canonical]

    return result


def install() -> None:
    from edward.ui import portfolio_page_v03
    portfolio_page_v03.build_cost_basis = robust_build_cost_basis
