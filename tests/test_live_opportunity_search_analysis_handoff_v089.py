from types import SimpleNamespace

from edward.services.opportunity_search_service_live_v04 import _ProvidedAnalysisService


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
