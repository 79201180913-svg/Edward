from __future__ import annotations

from decimal import Decimal

from edward.ui.stop_orders_page_v03 import _decimal, _kind, _side, _status


def test_stop_order_helpers_normalize_contract_values():
    assert _kind("STOP_ORDER_TYPE_STOP_LOSS") == "Стоп-лосс"
    assert _kind("STOP_ORDER_TYPE_TAKE_PROFIT") == "Тейк-профит"
    assert _kind("STOP_ORDER_TYPE_STOP_LIMIT") == "Стоп-лимит"
    assert _side("STOP_ORDER_DIRECTION_SELL") == "Продажа"
    assert _side("STOP_ORDER_DIRECTION_BUY") == "Покупка"
    assert _status("STOP_ORDER_STATUS_ACTIVE") == "Активна"
    assert _decimal({"units": "130", "nano": 500000000}) == Decimal("130.5")
