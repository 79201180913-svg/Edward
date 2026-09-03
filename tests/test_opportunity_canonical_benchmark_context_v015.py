from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015


def test_adapter_uses_benchmark_context_from_instrument(monkeypatch):
    captured = {}

    def fake_analyze_paths(self, **kwargs):
        captured.update(kwargs)
        return ()

    monkeypatch.setattr(
        "edward.services.opportunity_canonical_analysis_adapter_v015.AnalysisPathRuntimeServiceV012.analyze_paths",
        fake_analyze_paths,
    )
    CanonicalOpportunityAnalysisV015.clear_cache()

    candles = ("instrument-candle",)
    benchmark_candles = ("benchmark-candle",)
    instrument = {
        "benchmark_id": "IMOEX",
        "benchmark_candles": benchmark_candles,
    }

    result = CanonicalOpportunityAnalysisV015.analyze(
        instrument_uid="uid",
        ticker="SBER",
        candles=candles,
        profile="medium_term",
        instrument=instrument,
        force_recompute=True,
    )

    assert result.canonical_results == ()
    assert captured["benchmark_id"] == "IMOEX"
    assert captured["benchmark_candles"] == benchmark_candles


def test_explicit_benchmark_context_overrides_instrument_context(monkeypatch):
    captured = {}

    def fake_analyze_paths(self, **kwargs):
        captured.update(kwargs)
        return ()

    monkeypatch.setattr(
        "edward.services.opportunity_canonical_analysis_adapter_v015.AnalysisPathRuntimeServiceV012.analyze_paths",
        fake_analyze_paths,
    )
    CanonicalOpportunityAnalysisV015.clear_cache()

    CanonicalOpportunityAnalysisV015.analyze(
        instrument_uid="uid",
        ticker="SBER",
        candles=("instrument-candle",),
        instrument={"benchmark_id": "instrument-benchmark", "benchmark_candles": ("instrument-benchmark-candle",)},
        benchmark_id="explicit-benchmark",
        benchmark_candles=("explicit-benchmark-candle",),
        force_recompute=True,
    )

    assert captured["benchmark_id"] == "explicit-benchmark"
    assert captured["benchmark_candles"] == ("explicit-benchmark-candle",)
