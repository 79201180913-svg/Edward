from edward.services.instrument_decision_context_service import InstrumentDecisionContextService


def test_ui_instrument_flags_are_mapped_to_decision_context():
    context = InstrumentDecisionContextService().build(
        {
            "uid": "uid-unac",
            "ticker": "UNAC",
            "buy_available": True,
            "sell_available": True,
            "api_trade_available": True,
        },
        {
            "api_trade_available_flag": True,
            "trading_status": "SECURITY_TRADING_STATUS_NORMAL_TRADING",
        },
    )

    assert context.instrument_uid == "uid-unac"
    assert context.ticker == "UNAC"
    assert context.buy_available is True
    assert context.sell_available is True
    assert context.available is True
