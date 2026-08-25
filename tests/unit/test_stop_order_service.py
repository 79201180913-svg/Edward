from decimal import Decimal

import pytest

from edward.services.stop_order_service import (
    StopOrderKind,
    StopOrderRequest,
    StopOrderService,
    StopOrderSide,
)


class FakeGateway:
    def __init__(self):
        self.created = []
        self.cancelled = []

    def post_stop_order(self, request):
        self.created.append(request)
        return {"stop_order_id": "stop-1"}

    def get_stop_orders(self, account_id):
        return {"stop_orders": []}

    def cancel_stop_order(self, account_id, stop_order_id):
        self.cancelled.append((account_id, stop_order_id))
        return {"time": "now"}


def test_stop_loss_request_builds_market_child_order():
    gateway = FakeGateway()
    service = StopOrderService(gateway)
    result = service.create_protection(
        StopOrderRequest(
            account_id="acc",
            instrument_uid="uid",
            side=StopOrderSide.SELL,
            kind=StopOrderKind.STOP_LOSS,
            quantity=10,
            stop_price=Decimal("290"),
        )
    )

    assert result["stop_order_id"] == "stop-1"
    payload = gateway.created[0]
    assert payload["stop_order_type"] == "STOP_ORDER_TYPE_STOP_LOSS"
    assert payload["exchange_order_type"] == "EXCHANGE_ORDER_TYPE_MARKET"
    assert payload["expiration_type"] == "STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL"
    assert payload["direction"] == "STOP_ORDER_DIRECTION_SELL"
    assert payload["stop_price"] == Decimal("290")
    assert payload["price"] is None


def test_take_profit_request_uses_regular_take_profit_type():
    gateway = FakeGateway()
    service = StopOrderService(gateway)
    service.create_protection(
        StopOrderRequest(
            account_id="acc",
            instrument_uid="uid",
            side=StopOrderSide.SELL,
            kind=StopOrderKind.TAKE_PROFIT,
            quantity=5,
            stop_price=Decimal("350"),
        )
    )

    payload = gateway.created[0]
    assert payload["stop_order_type"] == "STOP_ORDER_TYPE_TAKE_PROFIT"
    assert payload["take_profit_type"] == "TAKE_PROFIT_TYPE_REGULAR"
    assert payload["exchange_order_type"] == "EXCHANGE_ORDER_TYPE_MARKET"


def test_stop_limit_request_builds_limit_child_order():
    gateway = FakeGateway()
    service = StopOrderService(gateway)
    service.create_protection(
        StopOrderRequest(
            account_id="acc",
            instrument_uid="uid",
            side=StopOrderSide.SELL,
            kind=StopOrderKind.STOP_LIMIT,
            quantity=10,
            stop_price=Decimal("290"),
            price=Decimal("289"),
        )
    )

    payload = gateway.created[0]
    assert payload["stop_order_type"] == "STOP_ORDER_TYPE_STOP_LIMIT"
    assert payload["exchange_order_type"] == "EXCHANGE_ORDER_TYPE_LIMIT"
    assert payload["stop_price"] == Decimal("290")
    assert payload["price"] == Decimal("289")


def test_stop_limit_requires_limit_price():
    with pytest.raises(ValueError, match="Цена лимитной заявки обязательна"):
        StopOrderRequest(
            "acc",
            "uid",
            StopOrderSide.SELL,
            StopOrderKind.STOP_LIMIT,
            1,
            Decimal("290"),
        )


def test_stop_order_request_rejects_non_positive_quantity():
    with pytest.raises(ValueError, match="Количество лотов"):
        StopOrderRequest("acc", "uid", StopOrderSide.SELL, StopOrderKind.STOP_LOSS, 0, Decimal("290"))


def test_stop_order_request_rejects_non_positive_price():
    with pytest.raises(ValueError, match="Стоп-цена"):
        StopOrderRequest("acc", "uid", StopOrderSide.SELL, StopOrderKind.STOP_LOSS, 1, Decimal("0"))
