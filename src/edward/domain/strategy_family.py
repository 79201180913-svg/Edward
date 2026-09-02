from __future__ import annotations

from enum import StrEnum


class StrategyFamily(StrEnum):
    """Research family describing the market behavior a hypothesis targets."""

    TREND_FOLLOWING = "Trend Following"
    MOMENTUM = "Momentum"
    BREAKOUT = "Breakout"
    MEAN_REVERSION = "Mean Reversion"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """Return the legacy fixed strategy families only.

        Adaptive Discovery is resolved by strategy_family_for_hypothesis() but is
        intentionally not added to the legacy enum contract used by v0.12 callers.
        """
        return tuple(item.value for item in cls)


STRATEGY_FAMILY_BY_HYPOTHESIS: dict[str, StrategyFamily] = {
    "BREAKOUT_EXPANSION": StrategyFamily.BREAKOUT,
    "RANGE_BREAK": StrategyFamily.BREAKOUT,
    "IMPULSE_CONTINUATION": StrategyFamily.MOMENTUM,
    "PULLBACK_RECLAIM": StrategyFamily.MEAN_REVERSION,
    "SHOCK_REVERSAL": StrategyFamily.MEAN_REVERSION,
    "GAP_REVERSAL": StrategyFamily.MEAN_REVERSION,
}


ADAPTIVE_DISCOVERY_FAMILY = "Adaptive Discovery"


def strategy_family_for_hypothesis(hypothesis: str) -> StrategyFamily | str | None:
    key = hypothesis.upper()
    if key.startswith("ADAPTIVE_RULE:"):
        return ADAPTIVE_DISCOVERY_FAMILY
    return STRATEGY_FAMILY_BY_HYPOTHESIS.get(key)


__all__ = [
    "ADAPTIVE_DISCOVERY_FAMILY",
    "STRATEGY_FAMILY_BY_HYPOTHESIS",
    "StrategyFamily",
    "strategy_family_for_hypothesis",
]
