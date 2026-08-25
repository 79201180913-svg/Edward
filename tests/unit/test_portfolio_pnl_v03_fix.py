from decimal import Decimal

from edward.ui.portfolio_pnl_v03_fix import calculate_pnl_row


def test_pnl_is_derived_from_average_price_when_yield_is_absent():
    result = calculate_pnl_row(
        {"average_position_price": {"units": "100", "nano": 0}},
        Decimal("10"),
        Decimal("110"),
    )
    assert result["average_price"] == Decimal("100")
    assert result["pnl"] == Decimal("100")
    assert result["pnl_percent"] == Decimal("10")


def test_average_price_is_derived_from_pnl_when_average_is_absent():
    result = calculate_pnl_row(
        {"expected_yield": {"units": "100", "nano": 0}},
        Decimal("10"),
        Decimal("110"),
    )
    assert result["pnl"] == Decimal("100")
    assert result["average_price"] == Decimal("100")


def test_missing_pnl_and_average_are_not_presented_as_zero():
    result = calculate_pnl_row({}, Decimal("10"), Decimal("110"))
    assert result["average_price"] is None
    assert result["pnl"] is None
    assert result["pnl_percent"] is None
