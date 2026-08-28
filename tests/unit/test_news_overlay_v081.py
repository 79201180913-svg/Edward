from types import SimpleNamespace

from edward.services.decision_engine import OpportunityContext
from edward.services.news_intelligence_service_v081 import NewsIntelligenceServiceV081
from edward.services.news_overlay_service_v081 import NewsOverlayServiceV081
from edward.services.opportunity_engine import OpportunityResult


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
    return SimpleNamespace(opportunity=opportunity)


def test_priority_news_reduces_score_and_can_block_entry():
    news = NewsIntelligenceServiceV081.analyze(
        [
            {"id": 1, "title": "important", "priority": True, "ts": "2026-08-28T10:00:00Z"},
            {"id": 2, "title": "important", "priority": True, "ts": "2026-08-28T11:00:00Z"},
            {"id": 3, "title": "important", "priority": True, "ts": "2026-08-28T12:00:00Z"},
            {"id": 4, "title": "important", "priority": True, "ts": "2026-08-28T13:00:00Z"},
            {"id": 5, "title": "important", "priority": True, "ts": "2026-08-28T14:00:00Z"},
            {"id": 6, "title": "important", "priority": True, "ts": "2026-08-28T15:00:00Z"},
            {"id": 7, "title": "important", "priority": True, "ts": "2026-08-28T16:00:00Z"},
            {"id": 8, "title": "important", "priority": True, "ts": "2026-08-28T17:00:00Z"},
        ],
        as_of="2026-08-28T18:00:00+00:00" if False else None,
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
