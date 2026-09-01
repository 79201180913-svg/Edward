from types import SimpleNamespace

from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathAnalysisV012,
    TradingPathMarketContext,
    TradingPathOpportunity,
    TradingPathValidationSummary,
)
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


def _canonical():
    path = TradingPathAnalysisV012(
        instrument_uid="SBER",
        ticker="SBER",
        strategy_family="H1",
        hypothesis="BREAKOUT_EXPANSION",
        regime="RANGE",
        volatility_bucket="High",
        direction="Positive",
        horizon=5,
        evidence=SimpleNamespace(),
        validation=TradingPathValidationSummary(
            wf_persistence_pct=100.0,
            positive_oos_windows_pct=100.0,
            statistical_valid=True,
            overlap_valid=True,
            multiple_testing_valid=False,
        ),
        market_context=TradingPathMarketContext(context_rank=2, rank_delta=-1),
        opportunity=TradingPathOpportunity(score=64.0, confidence=72.0, expected_value_pct=2.4, risk_score=31.0, risk_gate=True),
        current_state=TradingPathCurrentState.WAIT,
        decision=TradingPathDecision.WAIT,
        status=TradingPathAnalysisStatus.VALIDATED,
        rank=1,
    )
    return SimpleNamespace(
        instrument_uid="SBER",
        ticker="SBER",
        decision=TradingPathDecision.WAIT,
        current_state=TradingPathCurrentState.WAIT,
        best_path=path,
        total_paths=4,
        promoted_paths=0,
        research_only_paths=3,
        rejected_paths=1,
    )


def test_live_opportunity_maps_canonical_trading_path_without_legacy_fields():
    service = object.__new__(LiveOpportunitySearchService)
    item = service._canonical_result(SimpleNamespace(uid="SBER", ticker="SBER", name="Sber", last_price=300.0), _canonical(), 0.0)

    assert item.ticker == "SBER"
    assert item.decision == "WAIT"
    assert item.canonical_opportunity.best_path.hypothesis == "BREAKOUT_EXPANSION"
    assert item.opportunity_score == 64.0
    assert item.risk_score == 31.0
    assert item.forecast_model is None
    assert item.trade_plan is None


def test_opportunity_ui_source_uses_trading_path_columns():
    from pathlib import Path

    source = Path("src/edward/ui/opportunity_search_ui_v04.py").read_text(encoding="utf-8")

    assert "Лучший Trading Path" in source
    assert "Expected Value" in source
    assert "Multiple Testing" in source
    assert "Прогноз 5Д" not in source
    assert "Балл стратегии" not in source
    assert "Балл возможности" not in source
