from decimal import Decimal

import pytest

from edward.services.order_service import OrderRequest, OrderSide, OrderType


def test_stop_price_is_rejected_by_orders_service_request():
    with pytest.raises(ValueError, match="stop_price is only valid for StopOrdersService requests"):
        OrderRequest(
            "acc",
            "uid",
            OrderSide.BUY,
            OrderType.LIMIT,
            1,
            price=Decimal("10.01"),
            stop_price=Decimal("10.02"),
        )


def test_stop_order_types_are_not_part_of_orders_service_contract():
    assert not hasattr(OrderType, "STOP")
    assert not hasattr(OrderType, "STOP_LIMIT")
