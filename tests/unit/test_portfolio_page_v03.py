from decimal import Decimal

from edward.ui.portfolio_page_v03 import position_metrics


def test_position_metrics_uses_expected_yield_and_average_price():
    result = position_metrics(
        {
            "balance": "10",
            "current_price": "140.00",
            "average_position_price": "120.00",
            "expected_yield": "200.00",
        }
    )

    assert result["quantity"] == Decimal("10")
    assert result["market_value"] == Decimal("1400.00")
    assert result["pnl"] == Decimal("200.00")
    assert abs(result["pnl_pct"] - Decimal("16.6666666666666666666666666667")) < Decimal("1e-26")


def test_position_metrics_calculates_pnl_when_expected_yield_missing():
    result = position_metrics(
        {
            "balance": "10",
            "current_price": "140.00",
            "average_position_price": "120.00",
        }
    )

    assert result["market_value"] == Decimal("1400.00")
    assert result["pnl"] == Decimal("200.00")
    assert abs(result["pnl_pct"] - Decimal("16.6666666666666666666666666667")) < Decimal("1e-26")


def test_position_metrics_infers_average_price_from_expected_yield():
    result = position_metrics(
        {
            "balance": "10",
            "current_price": "140.00",
            "expected_yield": "200.00",
        }
    )

    assert result["average_price"] == Decimal("120.00")
    assert result["pnl"] == Decimal("200.00")


def test_position_metrics_returns_unknown_pnl_when_no_average_or_yield():
    result = position_metrics(
        {
            "balance": "10",
            "current_price": "140.00",
        }
    )

    assert result["market_value"] == Decimal("1400.00")
    assert result["average_price"] is None
    assert result["pnl"] is None
    assert result["pnl_pct"] is None
