from decimal import Decimal

from edward.ui.portfolio_page_v03 import build_cost_basis, position_metrics


def test_position_metrics_uses_expected_yield_and_average_price():
    result = position_metrics({"balance": "10", "current_price": "140.00", "average_position_price": "120.00", "expected_yield": "200.00"})
    assert result["quantity"] == Decimal("10")
    assert result["market_value"] == Decimal("1400.00")
    assert result["pnl"] == Decimal("200.00")
    assert abs(result["pnl_pct"] - Decimal("16.6666666666666666666666666667")) < Decimal("1e-26")


def test_position_metrics_calculates_pnl_when_expected_yield_missing():
    result = position_metrics({"balance": "10", "current_price": "140.00", "average_position_price": "120.00"})
    assert result["market_value"] == Decimal("1400.00")
    assert result["pnl"] == Decimal("200.00")
    assert abs(result["pnl_pct"] - Decimal("16.6666666666666666666666666667")) < Decimal("1e-26")


def test_position_metrics_infers_average_price_from_expected_yield():
    result = position_metrics({"balance": "10", "current_price": "140.00", "expected_yield": "200.00"})
    assert result["average_price"] == Decimal("120.00")
    assert result["pnl"] == Decimal("200.00")


def test_position_metrics_returns_unknown_pnl_when_no_average_or_yield():
    result = position_metrics({"balance": "10", "current_price": "140.00"})
    assert result["market_value"] == Decimal("1400.00")
    assert result["average_price"] is None
    assert result["pnl"] is None
    assert result["pnl_pct"] is None


def test_build_cost_basis_uses_weighted_average_for_buys():
    result = build_cost_basis([
        {"operation_type": 15, "instrument_uid": "A", "quantity": "10", "payment": {"units": "1000", "nano": 0}},
        {"operation_type": 15, "instrument_uid": "A", "quantity": "5", "payment": {"units": "600", "nano": 0}},
    ])
    assert result["A"]["quantity"] == Decimal("15")
    assert result["A"]["average_price"] == Decimal("106.6666666666666666666666666667")


def test_build_cost_basis_reduces_cost_on_sell_using_current_average():
    result = build_cost_basis([
        {"operation_type": 15, "instrument_uid": "A", "quantity": "10", "payment": {"units": "1000", "nano": 0}},
        {"operation_type": 22, "instrument_uid": "A", "quantity": "4", "payment": {"units": "600", "nano": 0}},
    ])
    assert result["A"]["quantity"] == Decimal("6")
    assert result["A"]["cost"] == Decimal("600")
    assert result["A"]["average_price"] == Decimal("100")
