from decimal import Decimal

from edward.ui.portfolio_pnl_v03 import _average_price, _pnl, _price, _quantity


def test_quantity_prefers_position_quantity():
    position = {"quantity": 12, "balance": 12}
    assert _quantity(position) == Decimal("12")


def test_price_reads_current_price():
    position = {"current_price": {"units": "140", "nano": 500000000}}
    assert _price(position) == Decimal("140.5")


def test_pnl_reads_expected_yield():
    position = {"expected_yield": {"units": "10", "nano": 500000000}}
    assert _pnl(position) == Decimal("10.5")


def test_average_price_uses_position_field():
    position = {"average_position_price": {"units": "130", "nano": 0}}
    assert _average_price(position, Decimal("10"), Decimal("140"), Decimal("100")) == Decimal("130")


def test_average_price_can_be_derived_from_pnl():
    position = {}
    assert _average_price(position, Decimal("10"), Decimal("140"), Decimal("100")) == Decimal("130")
