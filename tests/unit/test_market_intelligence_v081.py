from edward.services.market_intelligence_service_v081 import MarketIntelligenceServiceV081


def test_dividend_total_return_includes_price_and_dividend_components():
    result = MarketIntelligenceServiceV081.dividends(
        {"dividend_yield": 5.0, "dividend_growth": 8.0, "dividend_regularity": 90.0},
        price_return_pct=12.0,
    )

    assert result.total_return_pct == 17.0
    assert result.growth_score > 50
    assert result.stability_score > 50


def test_insider_net_value_distinguishes_large_buying():
    result = MarketIntelligenceServiceV081.insiders(
        [
            {"type": "BUY", "price": 100, "quantity": 1000},
            {"type": "BUY", "price": 100, "quantity": 500},
            {"type": "SELL", "price": 100, "quantity": 100},
        ]
    )

    assert result.net_direction == "BUY"
    assert result.net_buy_value == 150_000
    assert result.net_sell_value == 10_000


def test_session_intelligence_marks_clearing_as_not_executable():
    result = MarketIntelligenceServiceV081.session("CLEARING")

    assert result.auction_or_clearing is True
    assert result.execution_allowed is False
    assert result.quality_score == 0.0


def test_instrument_risk_prefers_client_specific_rates():
    result = MarketIntelligenceServiceV081.instrument_risk(
        {"dlong": 8, "dshort": 10, "dlong_client": 22, "dshort_client": 30, "short_enabled": True}
    )

    assert result.dlong_pct == 8
    assert result.dlong_client_pct == 22
    assert result.short_enabled is True
    assert result.risk_score > 50


def test_operations_calculate_net_economics_after_fees_and_taxes():
    result = MarketIntelligenceServiceV081.operations(
        [
            {"type": "BUY", "amount": 1000, "fee": 10},
            {"type": "SELL", "amount": 1200, "fee": 12, "tax": 8},
            {"type": "DIVIDEND", "amount": 50},
        ]
    )

    assert result.total_fees == 22
    assert result.total_taxes == 8
    assert result.total_dividends == 50
    assert result.realized_net_pnl == 210
    assert result.net_cash_impact == 260


def test_derivatives_expose_theoretical_price_gap_and_expiry_risk():
    result = MarketIntelligenceServiceV081.derivatives(
        {
            "kind": "OPTION",
            "open_interest": 5000,
            "bid_price": 9,
            "ask_price": 11,
            "theoretical_price": 10,
            "days_to_expiry": 2,
        }
    )

    assert result.available is True
    assert result.open_interest == 5000
    assert result.theoretical_price_gap_pct == 0.0
    assert result.expiration_risk_score == 90.0


def test_complete_market_intelligence_is_composable():
    result = MarketIntelligenceServiceV081.analyze(
        dividend_data={"dividend_yield": 4},
        dividend_event=True,
        insider_transactions=[{"type": "BUY", "price": 10, "quantity": 100}],
        session_name="REGULAR",
        risk_data={"dlong_client": 10, "dshort_client": 15, "short_enabled": True},
        operations=[{"type": "DIVIDEND", "amount": 25}],
        derivatives_data={"kind": "FUTURE", "open_interest": 2000, "days_to_expiry": 30},
    )

    assert result.dividends.upcoming_event is True
    assert result.insiders.net_direction == "BUY"
    assert result.session.execution_allowed is True
    assert result.instrument_risk.short_enabled is True
    assert result.operations.total_dividends == 25
    assert result.derivatives.available is True
