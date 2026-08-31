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


@dataclass(frozen=True, slots=True)
class TradingPathPromotionResultV088:
    status: TradingPathPromotionStatusV088
    reasons: tuple[str, ...]


class TradingPathPromotionGateV088:
    """Conservative gate from validated research evidence to promotion.

    Promotion is deliberately independent from the legacy strategy Quality Gate.
    This first step only uses evidence already produced by the v0.8.8 validation
    pipeline; temporal, overlap and multiple-testing evidence remain explicit
    reasons for research-only status until their dedicated stages are complete.
    """

    @staticmethod
    def evaluate(result, policy: TradingPathPromotionPolicyV088 | None = None) -> TradingPathPromotionResultV088:
        policy = policy or TradingPathPromotionPolicyV088()
        reasons: list[str] = []
        evidence = result.statistical_evidence
        if result.trades < policy.min_trades:
            reasons.append("LOW_SAMPLE")
        if result.net_return_pct <= policy.min_mean_return_pct:
            reasons.append("NON_POSITIVE_NET_RETURN")
        if policy.require_ci95_above_zero and evidence.ci95_low_pct <= 0:
            reasons.append("CI95_NOT_ABOVE_ZERO")
        # Until temporal/overlap/multiple-testing layers are implemented, a
        # validated path cannot be promoted to a production-capable state.
        reasons.extend(("TEMPORAL_EVIDENCE_REQUIRED", "OVERLAP_AUDIT_REQUIRED", "MULTIPLE_TESTING_AUDIT_REQUIRED"))
        status = TradingPathPromotionStatusV088.RESEARCH_ONLY
        if "LOW_SAMPLE" in reasons or "NON_POSITIVE_NET_RETURN" in reasons or "CI95_NOT_ABOVE_ZERO" in reasons:
            status = TradingPathPromotionStatusV088.REJECTED
        return TradingPathPromotionResultV088(status=status, reasons=tuple(dict.fromkeys(reasons)))


__all__ = ["TradingPathPromotionStatusV088", "TradingPathPromotionPolicyV088", "TradingPathPromotionResultV088", "TradingPathPromotionGateV088"]
