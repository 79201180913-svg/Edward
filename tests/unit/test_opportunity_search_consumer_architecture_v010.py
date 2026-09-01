from pathlib import Path

LIVE_SERVICE_PATH = Path("src/edward/services/opportunity_search_service_live_v04.py")


def _source() -> str:
    return LIVE_SERVICE_PATH.read_text(encoding="utf-8")


def test_live_opportunity_search_does_not_invoke_legacy_evaluation_path():
    source = _source()
    assert "self._evaluate_instrument(" not in source
    assert "OpportunityEngine.evaluate(" not in source
    assert "DecisionEngine.evaluate(" not in source
    assert "ForecastModelSelectionService" not in source
    assert "TradePlanService" not in source
    assert "PositionSizingService" not in source
    assert "OpportunityAnalysisPipelineV0821" not in source
    assert "UnifiedOpportunityEngineV0821" not in source


def test_live_opportunity_search_uses_canonical_trading_path_consumer():
    source = _source()
    assert "TradingPathOpportunityRuntimeServiceV013" in source
    assert "self.path_runtime.scan_instrument(" in source
    assert "self._canonical_result(" in source


def test_live_opportunity_search_does_not_replace_canonical_opportunity_with_local_scoring():
    source = _source()
    assert "UnifiedOpportunityEngineV0821" not in source
    assert "opportunity_search_module.OpportunityEngine" not in source
