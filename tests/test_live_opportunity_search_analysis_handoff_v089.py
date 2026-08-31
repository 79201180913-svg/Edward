from types import MethodType, SimpleNamespace

from edward.services.opportunity_search_service import OpportunitySearchResult, OpportunitySearchService
from edward.services.opportunity_search_service_live_v04 import _ProvidedAnalysisService, LiveOpportunitySearchService


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


def test_live_scan_calculates_analysis_once_and_hands_result_to_opportunity_flow(monkeypatch):
    service = object.__new__(LiveOpportunitySearchService)
    original_analysis = object()
    service.analysis = original_analysis
    service._provided_candles = {}

    class FakePipeline:
        def __init__(self):
            self.calls = []

        def analyze(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                pipeline_result=object(),
                strategies=(),
                market_regime="Trend",
                confidence="High",
            )

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

    seen = []

    def fake_evaluate(self, **_kwargs):
        seen.append(self.analysis)
        assert isinstance(self.analysis, _ProvidedAnalysisService)
        assert self.analysis.result is pipeline.calls[0]["analysis_result"]
        return OpportunitySearchResult(
            "uid-1",
            "TEST",
            "Test",
            10.0,
            "Trend",
            None,
            0.0,
            0.0,
            "PASS",
            "VALID",
            "",
            "",
            0,
        )

    service._evaluate_instrument = MethodType(fake_evaluate, service)
    service._forecast_quality_gate = MethodType(lambda self, *_args: (False, "НЕ ПРИМЕНИМ"), service)

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert len(pipeline.calls) == 1
    assert len(seen) == 1
    assert isinstance(seen[0], _ProvidedAnalysisService)
    assert service.analysis is original_analysis
    assert results[0].ticker == "TEST"
