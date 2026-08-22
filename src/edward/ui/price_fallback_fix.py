from __future__ import annotations

from decimal import Decimal
from typing import Any


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


def install_price_fallback() -> None:
    import edward.ui.ux_fixes as ux

    def load_current_price(client: Any, instrument_uid: str, instrument: Any) -> Decimal:
        selected = _decimal(_field(instrument, "last_price", 0))
        if selected > 0:
            print(f"[ORDER PRICE] uid={instrument_uid} source=selected_instrument price={selected}", flush=True)
            return selected

        try:
            response = client.get_last_prices([instrument_uid])
            prices = _items(response, "last_prices")
            if prices:
                price = _decimal(_field(prices[0], "price", _field(prices[0], "last_price", 0)))
                if price > 0:
                    print(f"[ORDER PRICE] uid={instrument_uid} source=last_prices price={price}", flush=True)
                    return price
        except Exception as exc:
            print(f"[ORDER PRICE] uid={instrument_uid} last_prices_error={type(exc).__name__}: {exc}", flush=True)

        try:
            response = client.get_close_prices([instrument_uid])
            prices = _items(response, "close_prices")
            if prices:
                item = prices[0]
                price = _decimal(_field(item, "price", 0))
                if price <= 0:
                    price = _decimal(_field(item, "evening_session_price", 0))
                if price > 0:
                    print(f"[ORDER PRICE] uid={instrument_uid} source=close_prices price={price}", flush=True)
                    return price
        except Exception as exc:
            print(f"[ORDER PRICE] uid={instrument_uid} close_prices_error={type(exc).__name__}: {exc}", flush=True)

        print(f"[ORDER PRICE] uid={instrument_uid} source=unavailable", flush=True)
        return Decimal("0")

    ux._load_current_price = load_current_price
