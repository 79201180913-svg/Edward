from decimal import Decimal

import pytest

from edward.services.error_policy import ApiErrorCategory, classify_api_error
from edward.services.preflight import PreflightContext, validate_order


def test_rate_limit_is_retryable():
    error = classify_api_error(429, "RESOURCE_EXHAUSTED", "rate limit")
    assert error.category is ApiErrorCategory.RATE_LIMIT
    assert error.retryable


def test_auth_is_not_retryable():
    error = classify_api_error(401, "UNAUTHENTICATED", "unauthorized")
    assert error.category is ApiErrorCategory.AUTH
    assert not error.retryable


def test_preflight_rejects_insufficient_buying_power():
    with pytest.raises(ValueError, match="Insufficient available funds"):
        validate_order(
            side="BUY",
            quantity=Decimal("10"),
            price=Decimal("100"),
            min_price_increment=Decimal("1"),
            context=PreflightContext(available_cash=Decimal("999"), estimated_total=Decimal("1000")),
        )


def test_preflight_rejects_blocked_sell_quantity():
    with pytest.raises(ValueError, match="Insufficient available position"):
        validate_order(
            side="SELL",
            quantity=Decimal("11"),
            price=Decimal("100"),
            min_price_increment=Decimal("1"),
            context=PreflightContext(available_quantity=Decimal("10")),
        )


def test_preflight_checks_increment():
    with pytest.raises(ValueError, match="min_price_increment"):
        validate_order(
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("10.05"),
            min_price_increment=Decimal("0.1"),
            context=PreflightContext(available_cash=Decimal("100"), estimated_total=Decimal("10.05")),
        )
