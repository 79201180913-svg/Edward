from types import SimpleNamespace

from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathAnalysisV012,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathOpportunity,
    TradingPathValidationSummary,
)
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.opportunity_analysis_pipeline_v0821 import UnifiedOpportunityEngineV0821
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015
from edward.services.opportunity_engine import OpportunityEngine as LegacyOpportunityEngine
from edward.services.opportunity_search_service import OpportunitySearchService


def _analysis(*, decision: TradingPathDecision, hypothesis: str, source: str, rank: int = 1):
    evidence = SimpleNamespace(
        mean_forward_return_pct=2.5,
        max_drawdown_pct=4.0,
        observations=12,
    )
    return TradingPathAnalysisV012(
        instrument_uid="uid",
        ticker="SBER",
        strategy_family="Adaptive Discovery" if source == "adaptive" else "Breakout",
        hypothesis=hypothesis,
        regime="TREND_DOWN",
        volatility_bucket="Adaptive" if source == "adaptive" else "High",
        direction="Positive",
        horizon=20,
        evidence=evidence,
        validation=TradingPathValidationSummary(
            robustness_score=80.0,
            positive_oos_windows_pct=100.0,
            statistical_valid=True,
            promotion_status="validated",
        ),
        opportunity=TradingPathOpportunity(
            score=73.5,
            confidence=0.75,
            expected_value_pct=2.0,
            risk_score=20.0,
            risk_gate=True,
        ),
        current_state=TradingPathCurrentState.ENTRY_READY,
        decision=decision,
        status=TradingPathAnalysisStatus.VALIDATED,
        rank=rank,
    )


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


def test_unified_opportunity_engine_returns_canonical_opportunity_without_recalculation(monkeypatch):
    analysis = CanonicalOpportunityAnalysisV015.from_analyses(
        [_analysis(decision=TradingPathDecision.BUY, hypothesis="BREAKOUT_EXPANSION", source="fixed")]
    )
    expected_opportunity = analysis.best_analysis.opportunity

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Legacy OpportunityEngine must not be called for canonical analysis")

    monkeypatch.setattr(LegacyOpportunityEngine, "evaluate", fail_legacy)

    result = UnifiedOpportunityEngineV0821.evaluate(
        analysis,
        candles=[],
        strategy_result=analysis.strategies[0],
    )

    assert result is expected_opportunity
    assert result.score == 73.5
    assert result.confidence == 0.75
    assert result.expected_value_pct == 2.0
    assert result.risk_score == 20.0
    assert result.risk_gate is True


def test_canonical_contract_preserves_adaptive_and_fixed_sources():
    fixed = _analysis(
        decision=TradingPathDecision.WAIT,
        hypothesis="BREAKOUT_EXPANSION",
        source="fixed",
        rank=1,
    )
    adaptive = _analysis(
        decision=TradingPathDecision.BUY,
        hypothesis="ADAPTIVE_RULE:regime=TREND_DOWN AND distance_to_low_20 <= 0.04",
        source="adaptive",
        rank=2,
    )

    view = CanonicalOpportunityAnalysisV015.from_analyses([fixed, adaptive])

    assert view.canonical_results == (fixed, adaptive)
    assert [item.parameters["source"] for item in view.strategies] == ["fixed", "adaptive"]
    assert view.strategies[0].quality_gate is True
    assert view.strategies[1].quality_gate is True
    assert view.best_analysis is fixed


def test_empty_canonical_result_does_not_create_opportunity():
    view = CanonicalOpportunityAnalysisV015.from_analyses([])

    assert view.pipeline_result is None
    assert view.opportunity is None
    assert view.strategies == ()
