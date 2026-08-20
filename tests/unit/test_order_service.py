from decimal import Decimal

from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.validation.order_validator import validate_price_step


class FakeGateway:
    def __init__(self):
        self.created = []

    def post_order(self, request):
        self.created.append(request)
        return {"order_id": request.request_id}

    def get_order_state(self, account_id, order_id):
        return {"account_id": account_id, "order_id": order_id}

    def get_orders(self, account_id):
        return []

    def cancel_order(self, account_id, order_id):
        return {"order_id": order_id}

    def replace_order(self, request, order_id):
        return {"order_id": order_id}


def test_market_buy():
    gateway = FakeGateway()
    service = OrderService(gateway)
    request = OrderRequest("acc", "uid", OrderSide.BUY, OrderType.MARKET, 10)
    result = service.create_order(request)
    assert result["order_id"] == request.request_id


def test_limit_price_step():
    validate_price_step(Decimal("100.00"), Decimal("0.01"))
