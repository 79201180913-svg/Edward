from edward.services.contract_evidence_mapper_v081 import (
    map_dividend,
    map_fundamentals,
    map_insider,
    map_news,
    map_order_book,
    map_risk_rates,
    map_signal,
    map_trades,
    quotation_to_float,
)


def test_quotation_to_float_supports_contract_units_and_nano():
    assert quotation_to_float({"units": "123", "nano": 500000000}) == 123.5


def test_fundamentals_mapper_uses_contract_field_names_and_fcf_margin():
    result = map_fundamentals(
        {
            "roe": 18.0,
            "roic": 15.0,
            "net_margin_mrq": 10.0,
            "one_year_annual_revenue_growth_rate": 12.0,
            "eps_change_five_years": 30.0,
            "ebitda_change_five_years": 25.0,
            "net_debt_to_ebitda": 1.0,
            "current_ratio_mrq": 1.8,
            "revenue_ttm": {"units": "100", "nano": 0},
            "free_cash_flow_ttm": {"units": "12", "nano": 0},
            "pe_ratio_ttm": 10.0,
            "price_to_sales_ttm": 2.0,
            "price_to_book_ttm": 1.5,
            "price_to_free_cash_flow_ttm": 12.0,
            "dividend_yield_daily_ttm": 5.0,
            "dividend_payout_ratio_fy": 40.0,
            "five_year_annual_dividend_growth_rate": 8.0,
        }
    )

    assert result["net_margin"] == 10.0
    assert result["revenue_growth"] == 12.0
    assert result["eps_growth"] == 30.0
    assert result["free_cash_flow"] == 12.0
    assert result["pe"] == 10.0


def test_risk_rates_mapper_extracts_nested_contract_values():
    result = map_risk_rates(
        {
            "risk_rates": [
                {
                    "long_risk_rate": {"value": {"units": "12", "nano": 0}},
                    "short_risk_rate": {"value": {"units": "20", "nano": 0}},
                    "short_enabled_flag": True,
                }
            ]
        }
    )

    assert result["dlong_client"] == 12
    assert result["dshort_client"] == 20
    assert result["short_enabled"] is True


def test_market_data_mappers_normalize_prices_and_quantities():
    order_book = map_order_book(
        {
            "bids": [{"price": {"units": "99", "nano": 500000000}, "quantity": "10"}],
            "asks": [{"price": {"units": "100", "nano": 0}, "quantity": "8"}],
        }
    )
    trades = map_trades(
        {"trades": [{"direction": "TRADE_DIRECTION_BUY", "quantity": "12"}]}
    )

    assert order_book["bids"][0]["price"] == 99.5
    assert order_book["asks"][0]["price"] == 100.0
    assert trades[0]["quantity"] == 12.0


def test_signal_dividend_insider_and_news_mappers_preserve_contract_fields():
    signal = map_signal(
        {
            "signal_id": "S1",
            "strategy_id": "ST1",
            "strategy_name": "Trend",
            "instrument_uid": "UID",
            "direction": "SIGNAL_DIRECTION_BUY",
            "initial_price": {"units": "100", "nano": 0},
            "target_price": {"units": "110", "nano": 0},
            "probability": {"units": "70", "nano": 0},
        }
    )
    dividend = map_dividend(
        {
            "yield_value": {"units": "5", "nano": 0},
            "regularity": {"units": "90", "nano": 0},
            "record_date": "2026-09-01T00:00:00Z",
        }
    )
    insider = map_insider(
        {
            "direction": "TRADE_DIRECTION_BUY",
            "price": {"units": "100", "nano": 0},
            "quantity": "100",
            "percentage": {"units": "1", "nano": 0},
        }
    )
    news = map_news({"id": 1, "source": "src", "title": "News", "priority": True, "ts": "2026-08-28T10:00:00Z"})

    assert signal["target_price"] == 110.0
    assert dividend["dividend_yield"] == 5.0
    assert insider["percentage"] == 1.0
    assert news["priority"] is True
