from types import MethodType, SimpleNamespace

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.opportunity_search_service import OpportunitySearchService
from edward.services.opportunity_search_service_live_v04 import _ProvidedAnalysisService, LiveOpportunitySearchService


def _canonical_result():
    return AnalysisPipelineV08Result(
        analysis=SimpleNamespace(
            recommendation="WAIT",
            score=71.5,
            market_regime="Trend",
            strategies=(),
        ),
        opportunity=SimpleNamespace(score=64.25),
        expected_value=SimpleNamespace(expected_value_pct=3.2),
        portfolio_impact=SimpleNamespace(marginal_risk_pct=0.4),
        forecast_quality_score=82.0,
        regime_confidence=61.0,
        evidence_strategy="Breakout",
        portfolio_context_available=True,
        confidence=SimpleNamespace(overall_confidence=73.5),
        trading_path_research=SimpleNamespace(status="READY"),
        version="0.8.0",
    )


def test_provided_analysis_service_returns_precomputed_result_without_recalculation():
    result = SimpleNamespace(pipeline_result=object())
    provider = _ProvidedAnalysisService(result)

    returned = provider.analyze(
        instrument_uid="uid-1",
        ticker="TEST",
        candles=[],
        profile="medium_term",
        instrument={},
    )

    assert returned is result


def test_live_handoff_provider_is_not_the_canonical_analysis_pipeline():
    result = object()
    provider = _ProvidedAnalysisService(result)

    assert provider.result is result
    assert provider.__class__.__name__ == "_ProvidedAnalysisService"


def test_live_scan_consumes_canonical_analysis_result_without_opportunity_recalculation(monkeypatch):
    service = object.__new__(LiveOpportunitySearchService)
    service.analysis = object()
    service._provided_candles = {}

    class FakePipeline:
        def __init__(self):
            self.calls = []
            self.result = _canonical_result()

        def analyze(self, **kwargs):
            self.calls.append(kwargs)
            return self.result

        def force_recompute(self):
            raise AssertionError("force_recompute must not run in this test")

    pipeline = FakePipeline()
    service.analysis_pipeline = pipeline
    service.client = SimpleNamespace()
    service._active_account = MethodType(lambda self: None, service)
    service._build_universe = MethodType(
        lambda self, **_kwargs: [
            {"uid": "uid-1", "ticker": "TEST", "name": "Test", "last_price": 10.0},
        ],
        service,
    )
    monkeypatch.setattr(
        OpportunitySearchService,
        "_get_candles",
        lambda self, instrument_uid: [object()] * 150,
    )
    service._forecast_quality_gate = MethodType(lambda self, *_args: (False, "НЕ ПРИМЕНИМ"), service)

    def fail_if_called(**_kwargs):
        raise AssertionError("legacy opportunity evaluation must not run")

    service._evaluate_instrument = fail_if_called

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert len(pipeline.calls) == 1
    assert pipeline.calls[0]["instrument_uid"] == "uid-1"
    assert results[0].ticker == "TEST"
    assert results[0].opportunity_score == 64.25
    assert results[0].decision == "WAIT"
