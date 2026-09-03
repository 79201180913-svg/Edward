from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathAnalysisV012,
    TradingPathContextV015,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathOpportunity,
    TradingPathValidationSummary,
)
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015


def _analysis() -> TradingPathAnalysisV012:
    evidence = type("Evidence", (), {"mean_forward_return_pct": 1.0, "max_drawdown_pct": 2.0, "observations": 3})()
    return TradingPathAnalysisV012(
        instrument_uid="uid",
        ticker="SBER",
        strategy_family="Adaptive Discovery",
        hypothesis="ADAPTIVE_RULE:test",
        regime="RANGE",
        volatility_bucket="Adaptive",
        direction="Positive",
        horizon=20,
        evidence=evidence,
        validation=TradingPathValidationSummary(),
        opportunity=TradingPathOpportunity(score=1.0),
        current_state=TradingPathCurrentState.WAIT,
        decision=TradingPathDecision.WAIT,
        status=TradingPathAnalysisStatus.DISCOVERED,
    )


def test_adapter_preserves_explicit_context_through_canonical_result(monkeypatch):
    analysis = _analysis()

    def fake_analyze_paths(self, **kwargs):
        assert kwargs["instrument_uid"] == "uid"
        assert kwargs["ticker"] == "SBER"
        return (analysis,)

    monkeypatch.setattr(AnalysisPathRuntimeServiceV012, "analyze_paths", fake_analyze_paths)
    CanonicalOpportunityAnalysisV015.clear_cache()
    context = TradingPathContextV015(
        fundamentals={"pe": 8.0},
        instrument_metadata={"uid": "uid"},
        news=("news",),
        news_overlay={"sentiment": "positive"},
        signals=("signal",),
        events=("event",),
        dividends=("dividend",),
        insider=("insider",),
        risk_metadata={"limit": 0.1},
        session={"status": "open"},
    )

    result = CanonicalOpportunityAnalysisV015.analyze(
        instrument_uid="uid",
        ticker="SBER",
        candles=(),
        context=context,
    )

    assert result.best_analysis is not None
    assert result.best_analysis.context is context


def test_adapter_cache_key_changes_when_context_changes(monkeypatch):
    calls = []
    analysis = _analysis()

    def fake_analyze_paths(self, **kwargs):
        calls.append(kwargs)
        return (analysis,)

    monkeypatch.setattr(AnalysisPathRuntimeServiceV012, "analyze_paths", fake_analyze_paths)
    CanonicalOpportunityAnalysisV015.clear_cache()
    first = TradingPathContextV015(fundamentals={"pe": 8.0})
    second = TradingPathContextV015(fundamentals={"pe": 12.0})

    CanonicalOpportunityAnalysisV015.analyze(instrument_uid="uid", ticker="SBER", candles=(), context=first)
    CanonicalOpportunityAnalysisV015.analyze(instrument_uid="uid", ticker="SBER", candles=(), context=first)
    CanonicalOpportunityAnalysisV015.analyze(instrument_uid="uid", ticker="SBER", candles=(), context=second)

    assert len(calls) == 2
