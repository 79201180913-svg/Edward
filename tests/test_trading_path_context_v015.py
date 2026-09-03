from edward.domain import TradingPathContextV015


def test_v015_context_envelope_preserves_all_supported_context_sources():
    values = {
        "fundamentals": object(),
        "instrument_metadata": object(),
        "news": object(),
        "news_overlay": object(),
        "signals": object(),
        "events": object(),
        "dividends": object(),
        "insider": object(),
        "risk_metadata": object(),
        "session": object(),
    }

    context = TradingPathContextV015(**values)

    for name, value in values.items():
        assert getattr(context, name) is value


def test_v015_context_envelope_is_optional_and_immutable():
    context = TradingPathContextV015()

    assert context.fundamentals is None
    assert context.instrument_metadata is None
    assert context.news is None
    assert context.news_overlay is None
    assert context.signals is None
    assert context.events is None
    assert context.dividends is None
    assert context.insider is None
    assert context.risk_metadata is None
    assert context.session is None

    try:
        context.news = object()
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("TradingPathContextV015 must be immutable")
