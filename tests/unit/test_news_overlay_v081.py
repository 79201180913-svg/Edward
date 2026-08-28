from datetime import datetime, timezone

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.confidence_service_v08 import ConfidenceResult
from edward.services.decision_engine import OpportunityContext
from edward.services.news_intelligence_service_v081 import NewsIntelligenceServiceV081
from edward.services.news_overlay_service_v081 import NewsOverlayServiceV081
from edward.services.opportunity_engine import OpportunityResult
from edward.services.expected_value_engine_v08 import ExpectedValueEngine
from edward.services.portfolio_impact_service_v08 import PortfolioImpactResult
from edward.services.analysis_service import AnalysisResult


def _pipeline(score=80.0):
    context = OpportunityContext(
        opportunity_score=score,
        entry_ok=True,
        risk_ok=True,
        strategy_ok=True,
        market_regime_compatible=True,
        critical_risk=False,
    )
    opportunity = OpportunityResult(context, score, True, True, "base", None)
    confidence = ConfidenceResult(overall_confidence=60.0, level="Medium", strategy_confidence=60.0, forecast_confidence=60.0, regime_confidence=60.0, portfolio_confidence=60.0)
    analysis = AnalysisResult(
        instrument_uid="UID", ticker="TEST", profile="medium_term", risk_profile="balanced", horizon="medium",
        market_regime="TREND_UP", recommendation="HOLD", confidence="Medium", score=score,
        strategies=(), explanation="base", created_at=datetime.now(timezone.utc), analysis_version="0.8.0",
    )
    impact = PortfolioImpactResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    return AnalysisPipelineV08Result(analysis, opportunity, ExpectedValueEngine.from_returns((1.0, -0.5)), impact, confidence=confidence)


def test_priority_news_reduces_score_and_can_block_entry():
    news = NewsIntelligenceServiceV081.analyze(
        [{"id": i, "title": "important", "priority": True, "ts": f"2026-08-28T{10+i:02d}:00:00Z"} for i in range(8)],
        as_of=datetime(2026, 8, 28, 18, tzinfo=timezone.utc),
    )

    adjusted, overlay = NewsOverlayServiceV081.apply(_pipeline(), news)

    assert adjusted.opportunity.score < 80
    assert overlay.priority_count == 8
    assert adjusted.opportunity.context.risk_ok is False
    assert adjusted.opportunity.context.entry_ok is False


def test_neutral_news_without_priority_does_not_block():
    news = NewsIntelligenceServiceV081.analyze(
        [{"id": 1, "title": "routine", "priority": False}],
    )

    adjusted, overlay = NewsOverlayServiceV081.apply(_pipeline(), news)

    assert adjusted.opportunity.context.risk_ok is True
    assert overlay.priority_count == 0
