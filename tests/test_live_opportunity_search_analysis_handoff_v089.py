from types import SimpleNamespace

from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService
from edward.services.opportunity_search_service import OpportunitySearchService


def test_live_scan_consumes_canonical_trading_path_result_without_legacy_opportunity_recalculation(monkeypatch):
    service = object.__new__(LiveOpportunitySearchService)
    service._provided_candles = {}
    service.client = SimpleNamespace()
    service._active_account = lambda: None
    service._build_universe = lambda **_kwargs: [
        {"uid": "uid-1", "ticker": "TEST", "name": "Test", "last_price": 10.0},
    ]

    canonical_path = SimpleNamespace(
        hypothesis="BREAKOUT_EXPANSION", strategy_family="BREAKOUT_EXPANSION",
        regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5,
        status=SimpleNamespace(value="promotable"),
        opportunity=SimpleNamespace(score=75.0, risk_score=20.0, risk_gate=True, confidence=80.0, expected_value_pct=3.2),
    )
    canonical = SimpleNamespace(
        best_path=canonical_path, decision=SimpleNamespace(value="buy"),
        current_state=SimpleNamespace(value="entry_ready"), total_paths=1,
        promoted_paths=1, research_only_paths=0, rejected_paths=0,
    )
    service.path_runtime = SimpleNamespace(scan_instrument=lambda **_kwargs: canonical)
    monkeypatch.setattr(OpportunitySearchService, "_get_candles", lambda self, instrument_uid: [object()] * 300)
    service._evaluate_instrument = lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy opportunity evaluation must not run"))

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert len(results) == 1
    assert results[0].ticker == "TEST"
    assert results[0].decision == "BUY"
    assert results[0].opportunity_score == 75.0
    assert results[0].canonical_opportunity is canonical
