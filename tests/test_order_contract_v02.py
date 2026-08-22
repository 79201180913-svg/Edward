from decimal import Decimal

import pytest

from edward.services.order_service import OrderRequest, OrderSide, OrderType
from edward.services.order_monitor import OrderMonitor
from edward.services.error_policy_v02 import ErrorCategory, classify_error
from edward.domain.order_state import OrderStatus


def test_orders_service_supports_bestprice_without_price():
    request = OrderRequest("acc", "uid", OrderSide.BUY, OrderType.BESTPRICE, 1)
    assert request.order_type is OrderType.BESTPRICE
    assert request.price is None


def test_market_and_bestprice_reject_price():
    with pytest.raises(ValueError):
        OrderRequest("acc", "uid", OrderSide.BUY, OrderType.MARKET, 1, Decimal("100"))
    with pytest.raises(ValueError):
        OrderRequest("acc", "uid", OrderSide.BUY, OrderType.BESTPRICE, 1, Decimal("100"))


def test_limit_requires_price():
    with pytest.raises(ValueError):
        OrderRequest("acc", "uid", OrderSide.BUY, OrderType.LIMIT, 1)


def test_stop_price_is_not_allowed_on_orders_service():
    with pytest.raises(ValueError):
        OrderRequest("acc", "uid", OrderSide.BUY, OrderType.LIMIT, 1, Decimal("100"), Decimal("99"))


def test_order_monitor_normalizes_rest_dict():
    response = {
        "execution_report_status": "EXECUTION_REPORT_STATUS_PARTIALLYFILL",
        "lots_requested": 10,
        "lots_executed": 4,
        "instrument_uid": "uid",
        "executed_order_price": {"units": "101", "nano": 500000000},
        "executed_commission": {"units": "1", "nano": 250000000},
    }
    snapshot = OrderMonitor._to_snapshot(response, "acc", "order")
    assert snapshot.status is OrderStatus.PARTIALLY_FILLED
    assert snapshot.requested_quantity == 10
    assert snapshot.filled_quantity == 4
    assert snapshot.remaining_quantity == 6
    assert snapshot.instrument_uid == "uid"


def test_order_monitor_normalizes_filled_dict():
    response = {"execution_report_status": "EXECUTION_REPORT_STATUS_FILL", "lots_requested": 3, "lots_executed": 3}
    snapshot = OrderMonitor._to_snapshot(response, "acc", "order")
    assert snapshot.status is OrderStatus.FILLED
    assert snapshot.is_terminal


def test_error_policy_classifies_rate_limit_as_retryable():
    error = RuntimeError("RESOURCE_EXHAUSTED")
    error.status_code = 429
    error.error_code = "RESOURCE_EXHAUSTED"
    decision = classify_error(error)
    assert decision.category is ErrorCategory.RATE_LIMIT
    assert decision.retryable


def test_error_policy_does_not_retry_auth():
    error = RuntimeError("unauthorized")
    error.status_code = 401
    error.error_code = "UNAUTHORIZED"
    decision = classify_error(error)
    assert decision.category is ErrorCategory.AUTH
    assert not decision.retryable
