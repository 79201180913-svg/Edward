from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


MARKET_CONTEXT_SHADOW_SCORING_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class MarketContextShadowScoreV011:
    """Hypothetical market-context score; never changes the production decision."""

    baseline_score: float
    context_adjusted_score: float
    score_delta: float
    baseline_rank: int
    context_rank: int
    rank_delta: int
    regime_compatibility: float | None
    relative_strength_component: float
    volatility_component: float
    confidence_hint_delta: float
    status: str = "SHADOW"
    version: str = MARKET_CONTEXT_SHADOW_SCORING_VERSION


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


class MarketContextShadowScoringServiceV011:
    """Measure how market context would alter research ranking without mutating QG.

    The coefficients are deliberately small because v0.11.0 is an A/B/shadow
    measurement layer, not a calibrated production decision model.
    """

    HYPOTHESIS_TO_STRATEGY = {
        "BREAKOUT_EXPANSION": "Breakout",
        "RANGE_BREAK": "Breakout",
        "PULLBACK_RECLAIM": "Mean Reversion",
        "SHOCK_REVERSAL": "Mean Reversion",
        "GAP_REVERSAL": "Mean Reversion",
        "IMPULSE_CONTINUATION": "Momentum",
    }

    @classmethod
    def _regime_component(cls, candidate: Any, snapshot: Any) -> tuple[float | None, float]:
        market_regime = getattr(getattr(snapshot, "market_regime", None), "result", None)
        compatibility = getattr(market_regime, "strategy_compatibility", None)
        if not isinstance(compatibility, dict):
            return None, 0.0
        strategy = cls.HYPOTHESIS_TO_STRATEGY.get(getattr(getattr(candidate, "candidate", candidate), "rule", candidate).hypothesis)
        if strategy is None or strategy not in compatibility:
            return None, 0.0
        score = float(compatibility[strategy])
        return score, (score - 50.0) * 0.08

    @staticmethod
    def _relative_strength_component(snapshot: Any) -> float:
        relative = getattr(snapshot, "relative_strength", None)
        excess = getattr(relative, "excess_return_pct", None)
        if excess is None:
            classification = getattr(relative, "classification", "")
            return 1.5 if classification == "OUTPERFORMING" else -1.5 if classification == "UNDERPERFORMING" else 0.0
        return _clamp(float(excess), -5.0, 5.0) * 0.30

    @staticmethod
    def _volatility_component(candidate: Any, snapshot: Any) -> float:
        volatility = getattr(snapshot, "volatility", None)
        classification = getattr(volatility, "classification", "")
        rule = getattr(getattr(candidate, "candidate", candidate), "rule", candidate)
        bucket = str(getattr(rule, "volatility_bucket", ""))
        if classification == "LOWER_THAN_MARKET":
            return 1.0 if bucket == "Normal" else -0.5 if bucket == "High" else 0.0
        if classification == "HIGHER_THAN_MARKET":
            return 1.0 if bucket == "High" else -0.5 if bucket == "Normal" else 0.0
        return 0.0

    @classmethod
    def score(cls, *, baseline: float, candidate: Any, snapshot: Any) -> tuple[float, float | None, float, float, float]:
        regime_compatibility, regime_component = cls._regime_component(candidate, snapshot)
        relative_strength_component = cls._relative_strength_component(snapshot)
        volatility_component = cls._volatility_component(candidate, snapshot)
        delta = regime_component + relative_strength_component + volatility_component
        adjusted = _clamp(baseline + delta)
        confidence_hint_delta = _clamp(delta, -5.0, 5.0) * 0.50
        return adjusted, regime_compatibility, relative_strength_component, volatility_component, confidence_hint_delta

    @classmethod
    def rank(cls, ranked: Iterable[Any], snapshot: Any) -> tuple[tuple[Any, MarketContextShadowScoreV011], ...]:
        baseline_items = tuple(ranked)
        if not baseline_items or snapshot is None or getattr(snapshot, "context_status", "UNAVAILABLE") != "FULL":
            return ()

        scored: list[tuple[Any, float, float | None, float, float, float]] = []
        for item in baseline_items:
            adjusted, regime_compatibility, relative_strength_component, volatility_component, confidence_hint_delta = cls.score(
                baseline=float(item.score),
                candidate=item,
                snapshot=snapshot,
            )
            scored.append((item, adjusted, regime_compatibility, relative_strength_component, volatility_component, confidence_hint_delta))

        score_order = sorted(
            scored,
            key=lambda row: (
                -row[1],
                row[0].candidate.rule.hypothesis,
                row[0].candidate.rule.regime,
                row[0].candidate.rule.volatility_bucket,
                row[0].candidate.rule.direction,
                row[0].candidate.rule.horizon,
            ),
        )
        context_position = {id(row[0]): index + 1 for index, row in enumerate(score_order)}

        result: list[tuple[Any, MarketContextShadowScoreV011]] = []
        for baseline_rank, row in enumerate(scored, 1):
            item, adjusted, regime_compatibility, relative_strength_component, volatility_component, confidence_hint_delta = row
            context_rank = context_position[id(item)]
            result.append((
                item,
                MarketContextShadowScoreV011(
                    baseline_score=round(float(item.score), 6),
                    context_adjusted_score=round(adjusted, 6),
                    score_delta=round(adjusted - float(item.score), 6),
                    baseline_rank=baseline_rank,
                    context_rank=context_rank,
                    rank_delta=baseline_rank - context_rank,
                    regime_compatibility=round(regime_compatibility, 6) if regime_compatibility is not None else None,
                    relative_strength_component=round(relative_strength_component, 6),
                    volatility_component=round(volatility_component, 6),
                    confidence_hint_delta=round(confidence_hint_delta, 6),
                ),
            ))
        return tuple(result)


__all__ = [
    "MARKET_CONTEXT_SHADOW_SCORING_VERSION",
    "MarketContextShadowScoreV011",
    "MarketContextShadowScoringServiceV011",
]
