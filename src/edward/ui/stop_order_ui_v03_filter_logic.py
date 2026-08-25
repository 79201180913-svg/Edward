from typing import Any


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def instrument_uid(order: Any) -> str:
    return str(_field(order, "instrument_uid", _field(order, "instrument_id", _field(order, "instrumentId", ""))))


def orders_for_instrument(orders: list[Any], uid: str) -> list[Any]:
    return [order for order in orders if instrument_uid(order) == str(uid)]
