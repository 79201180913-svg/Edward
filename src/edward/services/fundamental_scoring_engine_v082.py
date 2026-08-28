from __future__ import annotations

from math import isfinite


class FundamentalScoringEngineV082:
    """Pure metric scoring rules shared by the v0.8.2 fundamental layer."""

    @staticmethod
    def clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def _scale(cls, value: float, points: tuple[tuple[float, float], ...]) -> float:
        if not isfinite(value):
            return 0.0
        if value <= points[0][0]:
            return points[0][1]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if value <= x1:
                ratio = (value - x0) / (x1 - x0)
                return cls.clamp(y0 + ratio * (y1 - y0))
        return points[-1][1]

    @classmethod
    def profitability(cls, value: float, *, kind: str) -> float:
        """Score profitability ratios in percentage points using metric-specific curves."""
        curves = {
            "roe": ((-20.0, 15.0), (0.0, 25.0), (5.0, 38.0), (10.0, 52.0), (15.0, 64.0), (20.0, 74.0), (25.0, 82.0), (30.0, 88.0), (40.0, 94.0), (50.0, 98.0)),
            "roic": ((-20.0, 15.0), (0.0, 25.0), (5.0, 40.0), (10.0, 55.0), (15.0, 68.0), (20.0, 78.0), (25.0, 85.0), (30.0, 90.0), (40.0, 95.0), (50.0, 98.0)),
            "roa": ((-20.0, 15.0), (0.0, 25.0), (2.0, 40.0), (5.0, 55.0), (8.0, 68.0), (10.0, 75.0), (15.0, 86.0), (20.0, 93.0), (30.0, 98.0)),
            "net_margin": ((-30.0, 10.0), (-10.0, 25.0), (0.0, 40.0), (5.0, 52.0), (10.0, 64.0), (15.0, 74.0), (20.0, 82.0), (30.0, 91.0), (40.0, 96.0), (50.0, 98.0)),
        }
        if kind not in curves:
            raise ValueError(f"Unsupported profitability metric: {kind}")
        return cls._scale(value, curves[kind])

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
            return 50.0
        return 65.0 if value > 0 else 35.0 if value < 0 else 50.0

    @classmethod
    def fcf_yield(cls, value: float) -> float:
        if not isfinite(value):
            return 0.0
        return cls.clamp(50.0 + value * 5.0)

    @classmethod
    def roe_quality_adjustment(cls, roe: float | None, debt_to_equity: float | None) -> float:
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
    def momentum(cls, growth_5y: float | None, growth_3y: float | None, growth_1y: float | None, eps_growth: float | None, ebitda_growth: float | None) -> float:
        acceleration = cls.growth_acceleration(growth_5y, growth_3y, growth_1y)
        acceleration_score = cls.clamp(50.0 + acceleration * 2.5)
        earnings = [cls.growth(value) for value in (eps_growth, ebitda_growth) if value is not None and isfinite(value)]
        earnings_score = sum(earnings) / len(earnings) if earnings else 50.0
        return cls.clamp(acceleration_score * 0.65 + earnings_score * 0.35)

    @classmethod
    def fundamental_momentum(cls, *, revenue_acceleration: float, eps_growth: float | None, ebitda_growth: float | None, fcf_change: float | None = None, leverage_change: float | None = None) -> float:
        revenue_component = cls.clamp(50.0 + revenue_acceleration * 2.5)
        earnings = [cls.growth(v) for v in (eps_growth, ebitda_growth) if v is not None and isfinite(v)]
        earnings_component = sum(earnings) / len(earnings) if earnings else 50.0
        weighted = [(revenue_component, 0.50), (earnings_component, 0.30)]
        if fcf_change is not None and isfinite(fcf_change):
            weighted.append((cls.growth(fcf_change), 0.15))
        if leverage_change is not None and isfinite(leverage_change):
            weighted.append((cls.clamp(50.0 - leverage_change * 2.0), 0.05))
        total = sum(weight for _, weight in weighted)
        return cls.clamp(sum(score * weight for score, weight in weighted) / total)

    @classmethod
    def classify_acceleration(cls, acceleration: float) -> str:
        if acceleration > 2.0:
            return "FUNDAMENTAL_ACCELERATION"
        if acceleration < -2.0:
            return "FUNDAMENTAL_DECELERATION"
        return "FUNDAMENTAL_STABLE"


__all__ = ["FundamentalScoringEngineV082"]