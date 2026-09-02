from types import SimpleNamespace

from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015
from edward.services.opportunity_search_service import OpportunitySearchService


def test_opportunity_search_defaults_to_canonical_v014_analysis():
    service = OpportunitySearchService(client=object())

    assert service.analysis is CanonicalOpportunityAnalysisV015
    assert not service.analysis.__name__.endswith("V0821")


def test_canonical_opportunity_adapter_delegates_analysis_to_v014_runtime(monkeypatch):
    calls = {}
    expected = (SimpleNamespace(),)

    def fake_analyze_paths(self, **kwargs):
        calls.update(kwargs)
        return expected

    monkeypatch.setattr(AnalysisPathRuntimeServiceV012, "analyze_paths", fake_analyze_paths)

    result = CanonicalOpportunityAnalysisV015.analyze(
        instrument_uid="uid",
        ticker="SBER",
        candles=(1, 2, 3),
        profile="medium_term",
        instrument={"uid": "uid"},
    )

    assert calls == {
        "instrument_uid": "uid",
        "ticker": "SBER",
        "candles": (1, 2, 3),
        "profile": "medium_term",
    }
    assert result.analyses == expected
