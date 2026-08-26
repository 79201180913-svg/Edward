from types import SimpleNamespace

from edward.services.execution_opportunity_registry_v06 import ExecutionOpportunityRegistry
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService
from edward.ui.execution_opportunity_action_ui_v06 import _install_registry_scan_hook


def test_live_scan_results_are_published_to_execution_registry(monkeypatch):
    registry = ExecutionOpportunityRegistry()
    result = SimpleNamespace(instrument_uid="uid-1", ticker="TEST", decision="REDUCE", execution_ready=True, recommended_quantity=100)

    original_scan = LiveOpportunitySearchService.scan
    original_hook_flag = getattr(LiveOpportunitySearchService, "_execution_registry_hook_v06", False)
    original_registry = getattr(LiveOpportunitySearchService, "_execution_registry_v06", None)
    LiveOpportunitySearchService._execution_registry_hook_v06 = False

    def fake_scan(self, *args, **kwargs):
        return [result]

    monkeypatch.setattr(LiveOpportunitySearchService, "scan", fake_scan)
    try:
        _install_registry_scan_hook(registry)
        collected = LiveOpportunitySearchService.scan(object())
        assert collected == [result]
        assert registry.get("TEST") is result
    finally:
        LiveOpportunitySearchService.scan = original_scan
        LiveOpportunitySearchService._execution_registry_hook_v06 = original_hook_flag
        LiveOpportunitySearchService._execution_registry_v06 = original_registry
