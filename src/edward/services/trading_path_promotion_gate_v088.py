from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TradingPathPromotionStatusV088(str, Enum):
    PROMOTED = "promoted"
    RESEARCH_ONLY = "research_only"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TradingPathPromotionPolicyV088:
    min_trades: int = 10
    min_mean_return_pct: float = 0.0
    require_ci95_above_zero: bool = True
    require_temporal_stability: bool = True
    max_event_overlap_ratio: float = 0.0
    max_holding_overlap_ratio: float = 0.0


@dataclass(frozen=True, slots=True)
class TradingPathPromotionResultV088:
    status: TradingPathPromotionStatusV088
    reasons: tuple[str, ...]


class TradingPathPromotionGateV088:
    """Conservative gate from validated research evidence to promotion."""

    @staticmethod
    def evaluate(result, policy: TradingPathPromotionPolicyV088 | None = None, overlap=None) -> TradingPathPromotionResultV088:
        policy = policy or TradingPathPromotionPolicyV088()
        reasons: list[str] = []
        evidence = result.statistical_evidence
        if result.trades < policy.min_trades:
            reasons.append("LOW_SAMPLE")
        if result.net_return_pct <= policy.min_mean_return_pct:
            reasons.append("NON_POSITIVE_NET_RETURN")
        if policy.require_ci95_above_zero and evidence.ci95_low_pct <= 0:
            reasons.append("CI95_NOT_ABOVE_ZERO")

        temporal = getattr(result, "temporal_evidence", None)
        temporal_stable = bool(temporal is not None and temporal.temporal_stable)
        if policy.require_temporal_stability and not temporal_stable:
            reasons.append("TEMPORAL_EVIDENCE_REQUIRED")

        if overlap is None:
            reasons.append("OVERLAP_AUDIT_REQUIRED")
        else:
            if overlap.max_event_overlap_ratio > policy.max_event_overlap_ratio:
                reasons.append("EVENT_OVERLAP_TOO_HIGH")
            if overlap.max_holding_overlap_ratio > policy.max_holding_overlap_ratio:
                reasons.append("HOLDING_OVERLAP_TOO_HIGH")

        # Multiple-testing control remains an explicit hard requirement until
        # its evidence object is supplied by the dedicated audit layer.
        reasons.append("MULTIPLE_TESTING_AUDIT_REQUIRED")

        status = TradingPathPromotionStatusV088.RESEARCH_ONLY
        if "LOW_SAMPLE" in reasons or "NON_POSITIVE_NET_RETURN" in reasons or "CI95_NOT_ABOVE_ZERO" in reasons:
            status = TradingPathPromotionStatusV088.REJECTED
        return TradingPathPromotionResultV088(status=status, reasons=tuple(dict.fromkeys(reasons)))


__all__ = ["TradingPathPromotionStatusV088", "TradingPathPromotionPolicyV088", "TradingPathPromotionResultV088", "TradingPathPromotionGateV088"]
