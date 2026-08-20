from decimal import Decimal

import pytest

from edward.services.order_service import OrderRequest, OrderSide, OrderType
from edward.validation.trading_validator import TradingValidator, ValidationContext


class Provider:
    def __init__(self, context):
        self.context = context

    def get_validation_context(self, request):
        return self.context


def test_stop_price_must_match_increment():
    request = OrderRequest("acc", "uid", OrderSide.BUY, OrderType.STOP, 1, stop_price=Decimal("10.005"))
    provider = Provider(ValidationContext(True, True, price_increment=Decimal("0.01"), available_money=Decimal("100"), estimated_total=Decimal("10")))
    with pytest.raises(ValueError, match="Price must be a multiple"):
        TradingValidator(provider).validate(request)


def test_stop_limit_validates_both_prices():
    request = OrderRequest("acc", "uid", OrderSide.BUY, OrderType.STOP_LIMIT, 1, price=Decimal("10.01"), stop_price=Decimal("10.02"))
    provider = Provider(ValidationContext(True, True, price_increment=Decimal("0.01"), available_money=Decimal("100"), estimated_total=Decimal("10.01")))
    TradingValidator(provider).validate(request)
