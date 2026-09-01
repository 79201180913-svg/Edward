from types import SimpleNamespace

from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


def test_live_opportunity_service_uses_canonical_trading_path_runtime(monkeypatch):
    class FakeRuntime:
        def scan_instrument(self, **kwargs):
            return None

    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service.path_runtime = FakeRuntime()
    service._provided_candles = {}
    assert service.path_runtime is not None
