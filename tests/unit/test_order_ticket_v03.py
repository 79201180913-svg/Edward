from decimal import Decimal

import pytest

from edward.services.order_service import OrderRequest, OrderSide, OrderType


def test_market_order_has_no_price():
    request = OrderRequest(
        account_id="acc",
        instrument_uid="uid",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=2,
    )
    assert request.price is None


def test_bestprice_order_has_no_price():
    request = OrderRequest(
        account_id="acc",
        instrument_uid="uid",
        side=OrderSide.BUY,
        order_type=OrderType.BESTPRICE,
        quantity=3,
    )
    assert request.price is None


def test_limit_order_requires_positive_price():
    request = OrderRequest(
        account_id="acc",
        instrument_uid="uid",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=Decimal("100.50"),
    )
    assert request.price == Decimal("100.50")


def test_order_rejects_non_positive_quantity():
    with pytest.raises(ValueError, match="positive"):
        OrderRequest(
            account_id="acc",
            instrument_uid="uid",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0,
        )


def test_order_rejects_price_for_market_order():
    with pytest.raises(ValueError, match="Price must be omitted"):
        OrderRequest(
            account_id="acc",
            instrument_uid="uid",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1,
            price=Decimal("100"),
        )
