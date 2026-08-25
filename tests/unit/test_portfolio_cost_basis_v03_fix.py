from decimal import Decimal

from edward.ui.portfolio_cost_basis_v03_fix import robust_build_cost_basis


def test_robust_cost_basis_reads_trades_info_and_nested_instrument():
    result = robust_build_cost_basis([
        {
            "type": "OPERATION_TYPE_BUY",
            "instrument": {"instrument_uid": "UID-1", "figi": "FIGI-1", "ticker": "AAA"},
            "trades_info": {
                "trades": [
                    {"quantity": "4", "price": {"units": "120", "nano": 0}},
                    {"quantity": "6", "price": {"units": "130", "nano": 0}},
                ]
            },
        }
    ])
    assert result["UID-1"]["quantity"] == Decimal("10")
    assert result["UID-1"]["cost"] == Decimal("1260")
    assert result["UID-1"]["average_price"] == Decimal("126")
    assert result["FIGI-1"]["average_price"] == Decimal("126")
    assert result["AAA"]["average_price"] == Decimal("126")
