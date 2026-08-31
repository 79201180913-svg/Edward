from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TradingPathStatus(StrEnum):
    RESEARCH = "research"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TradingPathRule:
    """Explicit, testable rule contract produced from research evidence."""

    instrument_uid: str
    ticker: str
    hypothesis: str
    regime: str
    volatility_bucket: str
    direction: str
    horizon: int


@dataclass(frozen=True, slots=True)
class TradingPathEvidence:
    """Immutable evidence attached to one conditional trading path."""

    observations: int
    mean_forward_return_pct: float
    median_forward_return_pct: float
    win_rate_pct: float
    baseline_mean_return_pct: float
    excess_return_pct: float
    sufficient_sample: bool
    wf_persistence_pct: float | None = None


@dataclass(frozen=True, slots=True)
class TradingPathCandidate:
    """Research-to-validation bridge contract.

    A candidate is not a production recommendation. Promotion remains a separate
    validation step using the existing Walk Forward, robustness and Quality Gate.
    """

    rule: TradingPathRule
    evidence: TradingPathEvidence
    status: TradingPathStatus = TradingPathStatus.RESEARCH
    source_version: str = "0.8.6"


__all__ = [
    "TradingPathCandidate",
    "TradingPathEvidence",
    "TradingPathRule",
    "TradingPathStatus",
]
