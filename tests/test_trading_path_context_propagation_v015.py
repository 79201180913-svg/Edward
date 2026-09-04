from datetime import datetime, timezone
from types import SimpleNamespace

from edward.domain import TradingPathContextV015
from edward.services.analysis_service import Candle
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015, _context_from_instrument


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
    instrument = SimpleNamespace(uid="SBER", fundamentals=fundamentals, news=news)

    context = _context_from_instrument(instrument)

    assert context is not None
    assert context.instrument_metadata is instrument
    assert context.fundamentals is fundamentals
    assert context.news is news


def test_context_from_instrument_accepts_portfolio_context_fields():
    instrument = SimpleNamespace(
        uid="SBER",
        current_price=101.5,
        current_weight_pct=12.5,
        marginal_risk_pct=2.25,
        diversification_benefit_pct=0.75,
        expected_return_impact_pct=1.8,
        max_position_weight_pct=20.0,
    )

    context = _context_from_instrument(instrument)

    assert context is not None
    assert context.current_price == 101.5
    assert context.current_weight_pct == 12.5
    assert context.marginal_risk_pct == 2.25
    assert context.diversification_benefit_pct == 0.75
    assert context.expected_return_impact_pct == 1.8
    assert context.max_position_weight_pct == 20.0


def test_canonical_adapter_passes_context_into_runtime(monkeypatch):
    captured = {}
    candle = Candle(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1000.0,
    )
    context = TradingPathContextV015(fundamentals=object(), news=object(), session=object())
    analysis = SimpleNamespace(context=context)

    def analyze_paths(self, **kwargs):
        captured["context"] = kwargs["context"]
        return (analysis,)

    monkeypatch.setattr("edward.services.opportunity_canonical_analysis_adapter_v015.AnalysisPathRuntimeServiceV012.analyze_paths", analyze_paths)

    result = CanonicalOpportunityAnalysisV015.analyze(
        instrument_uid="SBER",
        ticker="SBER",
        candles=(candle,),
        context=context,
        force_recompute=True,
    )

    assert captured["context"] is context
    assert result.analyses[0].context is context
