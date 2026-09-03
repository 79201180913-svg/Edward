from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TradingPathAnalysisStatus(StrEnum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    PROMOTABLE = "promotable"
    PROMOTED = "promoted"
    REJECTED = "rejected"


class TradingPathCurrentState(StrEnum):
    ENTRY_READY = "entry_ready"
    WAIT = "wait"
    INVALID = "invalid"


class TradingPathDecision(StrEnum):
    BUY = "buy"
    WAIT = "wait"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class TradingPathValidationSummary:
    """Decision-independent validation snapshot for one trading path."""

    wf_persistence_pct: float | None = None
    robustness_score: float | None = None
    positive_oos_windows_pct: float | None = None
    statistical_valid: bool | None = None
    overlap_valid: bool | None = None
    multiple_testing_valid: bool | None = None
    promotion_status: str | None = None
    effective_sample_size: float | None = None
    overlap_ratio_pct: float | None = None
    standard_error_pct: float | None = None
    z_score: float | None = None
    p_value_one_sided: float | None = None
    adjusted_p_value: float | None = None
    hypotheses_tested: int | None = None


@dataclass(frozen=True, slots=True)
class TradingPathMarketContext:
    """Market-context snapshot used for path ranking."""

    benchmark_id: str | None = None
    baseline_rank: int | None = None
    context_rank: int | None = None
    rank_delta: int | None = None
    baseline_score: float | None = None
    context_adjusted_score: float | None = None
    score_delta: float | None = None
    regime_compatibility: float | None = None
    relative_strength_component: float | None = None
    volatility_component: float | None = None
    instrument_return_pct: float | None = None
    instrument_baseline_return_pct: float | None = None
    regime_baseline_return_pct: float | None = None
    market_return_pct: float | None = None
    instrument_excess_pct: float | None = None
    regime_excess_pct: float | None = None
    market_excess_pct: float | None = None
    relative_strength_pct: float | None = None
    context_status: str | None = None
    context_version: str | None = None


@dataclass(frozen=True, slots=True)
class TradingPathOpportunity:
    """Opportunity snapshot for one concrete trading path."""

    score: float | None = None
    confidence: float | None = None
    expected_value_pct: float | None = None
    risk_score: float | None = None
    risk_gate: bool | None = None


@dataclass(frozen=True, slots=True)
class TradingPathAnalysisV012:
    """Canonical v0.8.12 analysis contract."""

    instrument_uid: str
    ticker: str
    strategy_family: str
    hypothesis: str
    regime: str
    volatility_bucket: str
    direction: str
    horizon: int
    evidence: object
    validation: TradingPathValidationSummary = TradingPathValidationSummary()
    market_context: TradingPathMarketContext = TradingPathMarketContext()
    opportunity: TradingPathOpportunity = TradingPathOpportunity()
    current_state: TradingPathCurrentState = TradingPathCurrentState.WAIT
    decision: TradingPathDecision = TradingPathDecision.WAIT
    status: TradingPathAnalysisStatus = TradingPathAnalysisStatus.DISCOVERED
    rank: int | None = None
    independent_oos_evidence: object = None
    quality_gate: object = None


__all__ = [
    "TradingPathAnalysisStatus",
    "TradingPathCurrentState",
    "TradingPathDecision",
    "TradingPathValidationSummary",
    "TradingPathMarketContext",
    "TradingPathOpportunity",
    "TradingPathAnalysisV012",
]
