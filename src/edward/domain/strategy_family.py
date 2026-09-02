from __future__ import annotations

from enum import StrEnum


class StrategyFamily(StrEnum):
    """Research family describing the market behavior a hypothesis targets."""

    TREND_FOLLOWING = "Trend Following"
    MOMENTUM = "Momentum"
    BREAKOUT = "Breakout"
    MEAN_REVERSION = "Mean Reversion"
    ADAPTIVE_DISCOVERY = "Adaptive Discovery"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)


STRATEGY_FAMILY_BY_HYPOTHESIS: dict[str, StrategyFamily] = {
    "BREAKOUT_EXPANSION": StrategyFamily.BREAKOUT,
    "RANGE_BREAK": StrategyFamily.BREAKOUT,
    "IMPULSE_CONTINUATION": StrategyFamily.MOMENTUM,
    "PULLBACK_RECLAIM": StrategyFamily.MEAN_REVERSION,
    "SHOCK_REVERSAL": StrategyFamily.MEAN_REVERSION,
    "GAP_REVERSAL": StrategyFamily.MEAN_REVERSION,
    "ADAPTIVE_RULE": StrategyFamily.ADAPTIVE_DISCOVERY,
}


def strategy_family_for_hypothesis(hypothesis: str) -> StrategyFamily | None:
    key = hypothesis.upper()
    if key.startswith("ADAPTIVE_RULE:"):
        return StrategyFamily.ADAPTIVE_DISCOVERY
    return STRATEGY_FAMILY_BY_HYPOTHESIS.get(key)


__all__ = [
    "STRATEGY_FAMILY_BY_HYPOTHESIS",
    "StrategyFamily",
    "strategy_family_for_hypothesis",
]
