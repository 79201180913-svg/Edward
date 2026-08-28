from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Mapping, Sequence

NEWS_INTELLIGENCE_VERSION = "0.8.1"


def _value(data: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(data, Mapping) and name in data:
            return data[name]
        if hasattr(data, name):
            return getattr(data, name)
    return default


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


@dataclass(frozen=True, slots=True)
class NewsItemEvidence:
    news_id: str | None
    source: str | None
    timestamp: datetime | None
    priority: bool
    direction: str
    relevance: float
    sentiment_score: float | None


@dataclass(frozen=True, slots=True)
class NewsIntelligenceResult:
    items: tuple[NewsItemEvidence, ...]
    recent_count: int
    priority_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    relevance_score: float
    news_risk_score: float
    evidence_available: bool
    as_of: datetime
    version: str = NEWS_INTELLIGENCE_VERSION


class NewsIntelligenceServiceV081:
    """Interpret contract-provided news as time-bounded evidence.

    No opaque NLP model is assumed. Explicit sentiment fields are used when supplied;
    otherwise news is treated as neutral and contributes relevance/risk only.
    """

    @staticmethod
    def _direction(item: Any) -> tuple[str, float | None]:
        raw = _value(item, "sentiment", "direction", "tone", default=None)
        if raw is None:
            return "NEUTRAL", None
        text = str(raw).upper()
        if any(token in text for token in ("BUY", "POSITIVE", "GOOD", "UP", "BULL")):
            return "POSITIVE", 1.0
        if any(token in text for token in ("SELL", "NEGATIVE", "BAD", "DOWN", "BEAR")):
            return "NEGATIVE", -1.0
        return "NEUTRAL", 0.0

    @staticmethod
    def _timestamp(item: Any) -> datetime | None:
        value = _value(item, "ts", "timestamp", "created_at", default=None)
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @classmethod
    def analyze(
        cls,
        items: Sequence[Any] | None,
        *,
        instrument_uid: str | None = None,
        as_of: datetime | None = None,
        lookback_days: int = 30,
    ) -> NewsIntelligenceResult:
        now = as_of or datetime.now(timezone.utc)
        cutoff = now.timestamp() - max(1, lookback_days) * 86400
        parsed: list[NewsItemEvidence] = []
        for item in items or ():
            timestamp = cls._timestamp(item)
            if timestamp is not None and timestamp.timestamp() < cutoff:
                continue
            linked = _value(item, "instrument_id", "instruments", default=None)
            if instrument_uid is not None and linked is not None:
                linked_ids = linked if isinstance(linked, (list, tuple)) else [linked]
                normalized = [
                    _value(x, "instrument_uid", "uid", default=x) if not isinstance(x, str) else x
                    for x in linked_ids
                ]
                if instrument_uid not in normalized:
                    continue
            direction, sentiment = cls._direction(item)
            title = str(_value(item, "title", default=""))
            content = str(_value(item, "summary", "content", default=""))
            relevance = 50.0
            if title:
                relevance += 15.0
            if content:
                relevance += 10.0
            if bool(_value(item, "priority", default=False)):
                relevance += 25.0
            relevance = _clamp(relevance)
            parsed.append(
                NewsItemEvidence(
                    str(_value(item, "id", default="")) or None,
                    str(_value(item, "source", default="")) or None,
                    timestamp,
                    bool(_value(item, "priority", default=False)),
                    direction,
                    relevance,
                    sentiment,
                )
            )
        positives = sum(item.direction == "POSITIVE" for item in parsed)
        negatives = sum(item.direction == "NEGATIVE" for item in parsed)
        neutral = len(parsed) - positives - negatives
        priority = sum(item.priority for item in parsed)
        relevance = mean(item.relevance for item in parsed) if parsed else 0.0
        news_risk = _clamp(priority * 12.0 + max(0, len(parsed) - 20) * 1.5)
        return NewsIntelligenceResult(
            tuple(parsed),
            len(parsed),
            priority,
            positives,
            negatives,
            neutral,
            relevance,
            news_risk,
            bool(parsed),
            now,
        )


__all__ = ["NEWS_INTELLIGENCE_VERSION", "NewsItemEvidence", "NewsIntelligenceResult", "NewsIntelligenceServiceV081"]
