from __future__ import annotations

from math import isfinite
from typing import Mapping


class FundamentalScoringEngineV082:
    """Pure metric scoring rules shared by the v0.8.2 fundamental layer."""

    @staticmethod
    def clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def growth(cls, value: float) -> float:
        if not isfinite(value):
            return 0.0
        return cls.clamp(50.0 + value * 1.5)

    @classmethod
    def valuation(cls, value: float) -> float:
        if not isfinite(value):
            return 0.0
        if value <= 0:
            return 25.0
        return cls.clamp(90.0 - 2.0 * value)

    @classmethod
    def leverage(cls, value: float, *, scale: float = 18.0) -> float:
        if not isfinite(value):
            return 0.0
        return cls.clamp(90.0 - max(0.0, value) * scale)

    @classmethod
    def debt_to_equity(cls, value: float) -> float:
        if not isfinite(value):
            return 0.0
        return cls.clamp(90.0 - max(0.0, value) * 45.0)

    @classmethod
    def current_ratio(cls, value: float) -> float:
        if not isfinite(value):
            return 0.0
        if value <= 0:
            return 15.0
        return cls.clamp(55.0 + min(value - 1.0, 2.0) * 20.0)

    @classmethod
    def payout(cls, value: float) -> float:
        if not isfinite(value) or value < 0:
            return 25.0
        if value <= 60:
            return cls.clamp(85.0 - abs(value - 45.0) * 0.35)
        return cls.clamp(80.0 - (value - 60.0) * 1.4)

    @classmethod
    def cash_flow(cls, value: float) -> float:
        if not isfinite(value):
            return 0.0
        return 65.0 if value > 0 else 35.0 if value < 0 else 50.0

    @classmethod
    def fcf_yield(cls, value: float) -> float:
        if not isfinite(value):
            return 0.0
        return cls.clamp(50.0 + value * 5.0)

    @classmethod
    def roe_quality_adjustment(cls, roe: float | None, debt_to_equity: float | None) -> float:
        """Penalty when a high ROE is materially leverage-driven."""
        if roe is None or debt_to_equity is None or roe < 25.0 or debt_to_equity < 2.0:
            return 0.0
        return min(20.0, (debt_to_equity - 2.0) * 5.0)

    @classmethod
    def growth_acceleration(cls, growth_5y: float | None, growth_3y: float | None, growth_1y: float | None) -> float:
        changes = []
        if growth_5y is not None and growth_3y is not None:
            changes.append(growth_3y - growth_5y)
        if growth_3y is not None and growth_1y is not None:
            changes.append(growth_1y - growth_3y)
        return sum(changes) / len(changes) if changes else 0.0

    @classmethod
    def momentum(cls, *, metric_scores: Mapping[str, float], accelerations: tuple[float, ...] = ()) -> float:
        available = tuple(score for score in metric_scores.values() if isfinite(score))
        base = sum(available) / len(available) if available else 50.0
        acceleration_score = sum(accelerations) / len(accelerations) if accelerations else 50.0
        return cls.clamp(base * 0.7 + acceleration_score * 0.3)

    @classmethod
    def fundamental_momentum(
        cls,
        *,
        revenue_acceleration: float,
        eps_growth: float | None,
        ebitda_growth: float | None,
        fcf_change: float | None = None,
        leverage_change: float | None = None,
    ) -> float:
        """Combine operating acceleration with earnings/cash/debt direction."""
        revenue_component = cls.clamp(50.0 + revenue_acceleration * 2.5)
        earnings = [cls.growth(v) for v in (eps_growth, ebitda_growth) if v is not None and isfinite(v)]
        earnings_component = sum(earnings) / len(earnings) if earnings else 50.0
        components = [revenue_component * 0.50 + earnings_component * 0.30]
        if fcf_change is not None and isfinite(fcf_change):
            components.append(cls.growth(fcf_change) * 0.15)
        if leverage_change is not None and isfinite(leverage_change):
            # Negative change means falling leverage and is positive for health.
            components.append(cls.clamp(50.0 - leverage_change * 2.0) * 0.05)
        total_weight = 0.80 + (0.15 if fcf_change is not None and isfinite(fcf_change) else 0.0) + (0.05 if leverage_change is not None and isfinite(leverage_change) else 0.0)
        return cls.clamp(sum(components) / total_weight)

    @classmethod
    def classify_acceleration(cls, acceleration: float) -> str:
        if acceleration > 2.0:
            return "FUNDAMENTAL_ACCELERATION"
        if acceleration < -2.0:
            return "FUNDAMENTAL_DECELERATION"
        return "FUNDAMENTAL_STABLE"


__all__ = ["FundamentalScoringEngineV082"]
