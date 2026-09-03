from types import SimpleNamespace

from edward.domain import TradingPathContextV015
from edward.services.opportunity_canonical_analysis_adapter_v015 import _context_from_instrument


def test_context_from_instrument_preserves_all_supported_sources_by_identity():
    sources = {
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
    instrument = SimpleNamespace(uid="SBER", **sources)

    context = _context_from_instrument(instrument)

    assert isinstance(context, TradingPathContextV015)
    for name, source in sources.items():
        if name == "instrument_metadata":
            assert getattr(context, name) is instrument
        else:
            assert getattr(context, name) is source


def test_context_from_instrument_uses_instrument_as_metadata_without_dropping_explicit_sources():
    fundamentals = object()
    news = object()
    instrument = SimpleNamespace(
        uid="SBER",
        fundamentals=fundamentals,
        news=news,
    )

    context = _context_from_instrument(instrument)

    assert context is not None
    assert context.instrument_metadata is instrument
    assert context.fundamentals is fundamentals
    assert context.news is news
