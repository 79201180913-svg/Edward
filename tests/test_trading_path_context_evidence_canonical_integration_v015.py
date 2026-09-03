from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012, TradingPathContextV015
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015


def test_canonical_adapter_attaches_context_evidence(monkeypatch):
    context = TradingPathContextV015(fundamentals=object(), current_price=101.0)
    analysis = TradingPathAnalysisV012(
        instrument_uid="uid",
        ticker="TST",
        strategy_family="test",
        hypothesis="TEST",
        regime="RANGE",
        volatility_bucket="normal",
        direction="long",
        horizon=3,
        evidence=SimpleNamespace(),
    )
    captured = {}
    evidence = SimpleNamespace(version="0.8.15-context")

    def fake_runtime(self, **kwargs):
        captured.update(kwargs)
        return (analysis,)

    def fake_context_evidence(*, context, candles):
        captured["evidence_context"] = context
        captured["evidence_candles"] = candles
        return evidence

    monkeypatch.setattr(
        "edward.services.opportunity_canonical_analysis_adapter_v015.AnalysisPathRuntimeServiceV012.analyze_paths",
        fake_runtime,
    )
    monkeypatch.setattr(
        "edward.services.opportunity_canonical_analysis_adapter_v015.TradingPathContextEvidenceServiceV015.analyze",
        fake_context_evidence,
    )
    CanonicalOpportunityAnalysisV015.clear_cache()

    candles = (object(), object())
    result = CanonicalOpportunityAnalysisV015.analyze(
        instrument_uid="uid",
        ticker="TST",
        candles=candles,
        context=context,
        force_recompute=True,
    )

    assert result.canonical_results[0].context is context
    assert result.canonical_results[0].context_evidence is evidence
    assert captured["context"] is context
    assert captured["evidence_context"] is context
    assert captured["evidence_candles"] == candles
