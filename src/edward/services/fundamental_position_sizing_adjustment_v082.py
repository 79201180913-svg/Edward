from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FundamentalPositionSizingAdjustmentV082:
    multiplier: float
    adjusted_target_weight_pct: float
    capped: bool
    reason_codes: tuple[str, ...] = ()


class FundamentalPositionSizingAdjustmentServiceV082:
    """Conservative position-size adjustment from fundamental evidence.

    The adjustment can reduce a risk-derived target but can never increase it or
    bypass the risk engine's maximum position constraint.
    """

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, float(value)))

    @classmethod
    def calculate(
        cls,
        *,
        target_weight_pct: float,
        fundamental_score: float | None,
        business_quality_score: float | None,
        financial_health_score: float | None,
        max_position_weight_pct: float | None = None,
    ) -> FundamentalPositionSizingAdjustmentV082:
        target = max(0.0, float(target_weight_pct))
        if fundamental_score is None or business_quality_score is None or financial_health_score is None:
            adjusted = min(target, max_position_weight_pct) if max_position_weight_pct is not None else target
            return FundamentalPositionSizingAdjustmentV082(1.0 if target else 0.0, adjusted, adjusted != target, ("FUNDAMENTAL_DATA_UNAVAILABLE",))

        quality = cls._clamp(float(business_quality_score) / 100.0)
        health = cls._clamp(float(financial_health_score) / 100.0)
        overall = cls._clamp(float(fundamental_score) / 100.0)

        # Only weak evidence reduces size. Strong evidence never leverages the
        # position beyond the risk/planning target.
        weakness = max(0.0, 0.55 - min(quality, health, overall))
        multiplier = cls._clamp(1.0 - weakness * 1.25, 0.50, 1.0)
        adjusted = target * multiplier
        reasons: list[str] = []
        if multiplier < 1.0:
            reasons.append("FUNDAMENTAL_POSITION_REDUCTION")
        if health < 0.35:
            reasons.append("FINANCIAL_HEALTH_WEAK")
        if quality < 0.35:
            reasons.append("BUSINESS_QUALITY_WEAK")
        if overall < 0.40:
            reasons.append("FUNDAMENTALS_WEAK")

        capped = False
        if max_position_weight_pct is not None and adjusted > float(max_position_weight_pct):
            adjusted = float(max_position_weight_pct)
            capped = True
            reasons.append("RISK_POSITION_CAP")

        return FundamentalPositionSizingAdjustmentV082(round(multiplier, 4), round(adjusted, 4), capped, tuple(reasons))


__all__ = ["FundamentalPositionSizingAdjustmentV082", "FundamentalPositionSizingAdjustmentServiceV082"]
