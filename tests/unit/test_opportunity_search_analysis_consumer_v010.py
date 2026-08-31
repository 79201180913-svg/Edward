from types import SimpleNamespace

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.opportunity_search_analysis_consumer_v010 import OpportunityAnalysisConsumerV010


def _result():
    return AnalysisPipelineV08Result(
        analysis=SimpleNamespace(recommendation="BUY", score=71.5),
        opportunity=SimpleNamespace(score=64.25),
        expected_value=SimpleNamespace(expected_value_pct=3.2),
        portfolio_impact=SimpleNamespace(marginal_risk_pct=0.4),
        forecast_quality_score=82.0,
        regime_confidence=61.0,
        evidence_strategy="Breakout",
        portfolio_context_available=True,
        confidence=SimpleNamespace(overall_confidence=73.5),
        trading_path_research=SimpleNamespace(status="READY"),
        version="0.8.0",
    )


def test_consumer_exposes_canonical_result_without_recalculation():
    result = _result()

    view = OpportunityAnalysisConsumerV010.from_result(result)

    assert view.analysis_result is result
    assert view.analysis is result.analysis
    assert view.opportunity is result.opportunity
    assert view.expected_value is result.expected_value
    assert view.portfolio_impact is result.portfolio_impact
    assert view.forecast_quality_score == result.forecast_quality_score
    assert view.regime_confidence == result.regime_confidence
    assert view.evidence_strategy == result.evidence_strategy
    assert view.portfolio_context_available is True
    assert view.confidence is result.confidence
    assert view.trading_path_research is result.trading_path_research
    assert view.version == result.version


def test_consumer_rejects_non_canonical_result():
    try:
        OpportunityAnalysisConsumerV010.from_result(SimpleNamespace(opportunity=1))
    except TypeError as exc:
        assert "AnalysisPipelineV08Result" in str(exc)
    else:
        raise AssertionError("non-canonical analysis result must be rejected")
