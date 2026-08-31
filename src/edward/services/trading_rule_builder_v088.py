from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from edward.domain import TradingPathCandidate


class EntryTriggerV088(StrEnum):
    EVENT_CLOSE = "event_close"


class ExitTriggerV088(StrEnum):
    TIME_HORIZON = "time_horizon"


@dataclass(frozen=True, slots=True)
class TradingRuleV088:
    """Deterministic execution-neutral rule derived from one research candidate.

    The rule deliberately describes *when* a candidate would enter/exit without
    implementing an order or changing the production execution path.
    """

    instrument_uid: str
    ticker: str
    hypothesis: str
    regime: str
    volatility_bucket: str
    direction: str
    horizon: int
    entry_trigger: EntryTriggerV088
    exit_trigger: ExitTriggerV088


class TradingRuleBuilderV088:
    """Translate a research candidate into an explicit testable rule."""

    @staticmethod
    def build(candidate: TradingPathCandidate) -> TradingRuleV088:
        rule = candidate.rule
        if rule.horizon <= 0:
            raise ValueError("Trading path horizon must be positive")
        return TradingRuleV088(
            instrument_uid=rule.instrument_uid,
            ticker=rule.ticker,
            hypothesis=rule.hypothesis,
            regime=rule.regime,
            volatility_bucket=rule.volatility_bucket,
            direction=rule.direction,
            horizon=rule.horizon,
            entry_trigger=EntryTriggerV088.EVENT_CLOSE,
            exit_trigger=ExitTriggerV088.TIME_HORIZON,
        )


__all__ = [
    "EntryTriggerV088",
    "ExitTriggerV088",
    "TradingRuleV088",
    "TradingRuleBuilderV088",
]
