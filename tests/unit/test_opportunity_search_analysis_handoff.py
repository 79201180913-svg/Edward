from types import SimpleNamespace

from edward.services.opportunity_search_service import OpportunitySearchResult
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


def test_live_scan_calculates_canonical_path_once_and_consumes_the_same_result():
    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    service._provided_candles = {}
    calls = []

    path = SimpleNamespace(
        hypothesis="H1", strategy_family="H1", regime="Trend", volatility_bucket="Normal",
        direction="Positive", horizon=5, status=SimpleNamespace(value="promotable"),
        opportunity=SimpleNamespace(score=80.0, risk_score=20.0, risk_gate=True),
    )
    canonical = SimpleNamespace(
        best_path=path, decision=SimpleNamespace(value="buy"),
        current_state=SimpleNamespace(value="entry_ready"),
    )

    class FakeRuntime:
        def scan_instrument(self, **kwargs):
            calls.append(kwargs)
            return canonical

    service.path_runtime = FakeRuntime()
    service.client = SimpleNamespace()
    service._build_universe = lambda **_kwargs: [{"uid": "1", "ticker": "A", "name": "A", "last_price": "1"}]
    service._get_candles = lambda _uid: [object()] * 300

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert len(calls) == 1
    assert calls[0]["instrument_uid"] == "1"
    assert len(results) == 1
    assert results[0].ticker == "A"
    assert results[0].opportunity_score == 80.0
    assert results[0].decision == "BUY"


def test_live_scan_does_not_mutate_or_recompute_legacy_analysis_service():
    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    service._provided_candles = {}
    original_analysis = object()
    service.analysis = original_analysis
    canonical = SimpleNamespace(
        best_path=SimpleNamespace(
            hypothesis="H1", strategy_family="H1", regime="Trend", volatility_bucket="Normal",
            direction="Positive", horizon=5, status=SimpleNamespace(value="promotable"),
            opportunity=SimpleNamespace(score=80.0, risk_score=20.0, risk_gate=True),
        ),
        decision=SimpleNamespace(value="wait"), current_state=SimpleNamespace(value="wait"),
    )
    service.path_runtime = SimpleNamespace(scan_instrument=lambda **_kwargs: canonical)
    service.client = SimpleNamespace()
    service._build_universe = lambda **_kwargs: [{"uid": "1", "ticker": "A", "name": "A", "last_price": "1"}]
    service._get_candles = lambda _uid: [object()] * 300

    service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert service.analysis is original_analysis
