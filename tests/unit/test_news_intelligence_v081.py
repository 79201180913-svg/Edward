from datetime import datetime, timedelta, timezone

from edward.services.news_intelligence_service_v081 import NewsIntelligenceServiceV081


def test_news_filters_items_outside_lookback_and_unrelated_instrument():
    as_of = datetime(2026, 8, 28, tzinfo=timezone.utc)
    result = NewsIntelligenceServiceV081.analyze(
        [
            {"id": 1, "title": "A", "ts": as_of - timedelta(days=1), "instrument_id": [{"instrument_uid": "A"}]},
            {"id": 2, "title": "OLD", "ts": as_of - timedelta(days=31), "instrument_id": [{"instrument_uid": "A"}]},
            {"id": 3, "title": "OTHER", "ts": as_of - timedelta(days=1), "instrument_id": [{"instrument_uid": "B"}]},
        ],
        instrument_uid="A",
        as_of=as_of,
    )

    assert result.recent_count == 1
    assert result.items[0].news_id == "1"


def test_priority_news_increases_news_risk():
    as_of = datetime(2026, 8, 28, tzinfo=timezone.utc)
    normal = NewsIntelligenceServiceV081.analyze(
        [{"id": 1, "title": "routine", "ts": as_of, "priority": False}],
        as_of=as_of,
    )
    priority = NewsIntelligenceServiceV081.analyze(
        [{"id": 2, "title": "important", "ts": as_of, "priority": True}],
        as_of=as_of,
    )

    assert priority.news_risk_score > normal.news_risk_score
    assert priority.priority_count == 1


def test_explicit_sentiment_is_preserved():
    as_of = datetime(2026, 8, 28, tzinfo=timezone.utc)
    result = NewsIntelligenceServiceV081.analyze(
        [
            {"id": 1, "title": "good", "sentiment": "POSITIVE", "ts": as_of},
            {"id": 2, "title": "bad", "sentiment": "NEGATIVE", "ts": as_of},
        ],
        as_of=as_of,
    )

    assert result.positive_count == 1
    assert result.negative_count == 1
    assert result.neutral_count == 0
