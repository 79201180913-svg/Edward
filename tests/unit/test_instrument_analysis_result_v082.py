from types import SimpleNamespace

from edward.services.instrument_analysis_result_v082 import InstrumentAnalysisResultV082
from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisServiceV082
from edward.services.entry_quality_integration_v082 import EntryQualityIntegrationResult


def _fundamental():
    return FundamentalAnalysisServiceV082.analyze(
        {"roe": 20, "roic": 18, "revenue_growth": 15, "revenue_growth_3y": 12, "revenue_growth_5y": 10},
        profile="long_term",
    )


def _pipeline(fundamental, *, opportunity_score=80):
    opportunity = SimpleNamespace(score=opportunity_score, entry_signal=True, risk=SimpleNamespace(), explanation="ok")
    base = SimpleNamespace(
        analysis=SimpleNamespace(market_regime="BULLISH", trend="UP", momentum=75),
        opportunity=opportunity,
        confidence=82,
    )
    entry = EntryQualityIntegrationResult(
        entry_quality=SimpleNamespace(score=70, entry_blocked=False, entry_signal=True),
        opportunity_supported=True,
        reason_codes=(),
    )
    return SimpleNamespace(base=base, fundamental=fundamental, entry_quality=entry, opportunity_adjustment=None)


def test_unified_result_exposes_analysis_layers_without_budget_fields():
    result = InstrumentAnalysisResultV082.from_pipeline(
        instrument_uid="UID", ticker="ABC", pipeline_result=_pipeline(_fundamental())
    )
    assert result.instrument_uid == "UID"
    assert result.ticker == "ABC"
    assert result.fundamental.status == "PARTIAL"
    assert result.entry_quality.entry_quality.score == 70
    assert result.market["regime"] == "BULLISH"
    assert result.overall_score == 80
    assert not hasattr(result, "budget")
    assert not hasattr(result, "allocation")


def test_opportunity_remains_available_when_entry_is_not_confirmed():
    pipeline = _pipeline(_fundamental(), opportunity_score=87)
    pipeline.entry_quality = EntryQualityIntegrationResult(
        entry_quality=SimpleNamespace(score=30, entry_blocked=False, entry_signal=False),
        opportunity_supported=False,
        reason_codes=("ENTRY_NOT_CONFIRMED",),
    )
    result = InstrumentAnalysisResultV082.from_pipeline(
        instrument_uid="UID", ticker="ABC", pipeline_result=pipeline
    )
    assert result.overall_score == 87
    assert result.entry_quality.entry_quality.score == 30
    assert result.entry_quality.entry_quality.entry_signal is False
