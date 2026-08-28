from __future__ import annotations

from dataclasses import dataclass, replace

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.news_intelligence_service_v081 import NewsIntelligenceResult


@dataclass(frozen=True, slots=True)
class NewsOverlayResult:
    base_score: float
    adjusted_score: float
    news_risk_score: float
    recent_count: int
    priority_count: int
    conflict_penalty: float


class NewsOverlayServiceV081:
    """Apply contract-backed news risk without changing v0.8 public contracts."""

    @staticmethod
    def apply(pipeline: AnalysisPipelineV08Result, news: NewsIntelligenceResult) -> tuple[AnalysisPipelineV08Result, NewsOverlayResult]:
        base = float(pipeline.opportunity.score)
        if not news.evidence_available:
            return pipeline, NewsOverlayResult(base, base, 0.0, 0, 0, 0.0)

        sentiment_conflict = 0.0
        if news.positive_count and news.negative_count:
            sentiment_conflict = min(10.0, min(news.positive_count, news.negative_count) * 1.5)
        penalty = news.news_risk_score * 0.18 + sentiment_conflict
        adjusted_score = max(0.0, min(100.0, round(base - penalty, 2)))
        context = pipeline.opportunity.context
        if news.news_risk_score >= 90.0:
            context = replace(context, entry_ok=False, risk_ok=False)
        elif sentiment_conflict >= 6.0:
            context = replace(context, entry_ok=False)
        opportunity = replace(
            pipeline.opportunity,
            context=context,
            score=adjusted_score,
            explanation=(
                f"{pipeline.opportunity.explanation} News: risk={news.news_risk_score:.1f}, "
                f"recent={news.recent_count}, priority={news.priority_count}, conflict={sentiment_conflict:.1f}."
            ),
        )
        return replace(pipeline, opportunity=opportunity), NewsOverlayResult(
            base_score=base,
            adjusted_score=adjusted_score,
            news_risk_score=news.news_risk_score,
            recent_count=news.recent_count,
            priority_count=news.priority_count,
            conflict_penalty=sentiment_conflict,
        )


__all__ = ["NewsOverlayResult", "NewsOverlayServiceV081"]
