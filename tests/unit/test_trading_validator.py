from decimal import Decimal

import pytest

from edward.services.order_service import OrderRequest, OrderSide, OrderType
from edward.validation.trading_validator import TradingValidator, ValidationContext


class Provider:
    def __init__(self, context):
        self.context = context

    def get_validation_context(self, request):
        return self.context


def request(side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=10):
    return OrderRequest("acc", "uid", side, order_type, quantity, Decimal("10.00") if order_type == OrderType.LIMIT else None)


def test_buy_rejected_without_funds():
    provider = Provider(ValidationContext(True, True, available_money=Decimal("10"), estimated_total=Decimal("100")))
    with pytest.raises(ValueError, match="Insufficient available funds"):
        TradingValidator(provider).validate(request())


def test_sell_rejected_without_position():
    provider = Provider(ValidationContext(True, True, available_position=5))
    with pytest.raises(ValueError, match="Insufficient available position"):
        TradingValidator(provider).validate(request(OrderSide.SELL))


def test_limit_price_increment():
    provider = Provider(ValidationContext(True, True, price_increment=Decimal("0.01"), available_money=Decimal("1000"), estimated_total=Decimal("100")))
    TradingValidator(provider).validate(request(order_type=OrderType.LIMIT))
