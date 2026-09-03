from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from edward.services.expected_value_engine_v08 import ExpectedValueEngine, ExpectedValueResult


TRADING_PATH_EV_EVIDENCE_VERSION_V015 = "0.8.15"


@dataclass(frozen=True, slots=True)
class TradingPathEVEvidenceV015:
    """Decision-independent EV evidence for a trading path."""

    expected_value_pct: float | None
    ev_ci_low_pct: float | None
    ev_ci_high_pct: float | None
    observations: int
    edge_reliability_pct: float | None
    edge_reliability_level: str
    positive_ev: bool
    statistically_positive_ev: bool
    confidence_score: float
    confidence_level: str
    status: str
    version: str = TRADING_PATH_EV_EVIDENCE_VERSION_V015


class TradingPathEVEvidenceServiceV015:
    """Expose EV and uncertainty as explicit evidence without making a decision."""

    @staticmethod
    def _confidence_score(result: ExpectedValueResult) -> float:
        observations_score = min(float(result.observations) / 100.0, 1.0) * 40.0
        reliability_score = (float(result.edge_reliability_pct or 0.0) / 100.0) * 40.0
        ci_score = 20.0 if result.ev_ci_low_pct is not None and result.ev_ci_low_pct > 0.0 else 0.0
        return round(min(100.0, observations_score + reliability_score + ci_score), 2)

    @classmethod
    def build(cls, returns_pct: Sequence[float]) -> TradingPathEVEvidenceV015:
        result = ExpectedValueEngine.from_returns(tuple(float(value) for value in returns_pct))
        positive_ev = bool(result.available and result.expected_value_pct > 0.0)
        statistically_positive_ev = bool(
            positive_ev
            and result.ev_ci_low_pct is not None
            and result.ev_ci_low_pct > 0.0
        )
        if not result.available:
            status = "UNAVAILABLE"
        elif result.observations < 3:
            status = "INSUFFICIENT"
        else:
            status = "READY"
        confidence_score = cls._confidence_score(result)
        confidence_level = (
            "HIGH" if confidence_score >= 75.0
            else "MEDIUM" if confidence_score >= 50.0
            else "LOW"
        )
        return TradingPathEVEvidenceV015(
            expected_value_pct=result.expected_value_pct if result.available else None,
            ev_ci_low_pct=result.ev_ci_low_pct,
            ev_ci_high_pct=result.ev_ci_high_pct,
            observations=result.observations,
            edge_reliability_pct=result.edge_reliability_pct,
            edge_reliability_level=result.edge_reliability_level,
            positive_ev=positive_ev,
            statistically_positive_ev=statistically_positive_ev,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            status=status,
        )


__all__ = [
    "TRADING_PATH_EV_EVIDENCE_VERSION_V015",
    "TradingPathEVEvidenceV015",
    "TradingPathEVEvidenceServiceV015",
]
