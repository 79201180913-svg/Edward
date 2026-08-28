from dataclasses import fields

from edward.services.analysis_service import AnalysisResult, StrategyResult
from edward.services.opportunity_engine import OpportunityResult


def test_v081_does_not_remove_public_v08_analysis_fields():
    names = {field.name for field in fields(AnalysisResult)}
    assert {
        "instrument_uid", "ticker", "profile", "risk_profile", "horizon",
        "market_regime", "recommendation", "confidence", "score", "strategies",
        "explanation", "created_at", "analysis_version",
    } <= names


def test_v081_does_not_remove_public_v08_strategy_fields():
    names = {field.name for field in fields(StrategyResult)}
    assert {
        "strategy", "parameters", "return_pct", "max_drawdown_pct", "sharpe",
        "trades", "stability", "quality_gate", "score", "wf_windows",
    } <= names


def test_v081_keeps_opportunity_result_shape():
    names = {field.name for field in fields(OpportunityResult)}
    assert {"context", "score", "entry_signal", "market_regime_compatible", "explanation", "risk"} <= names
