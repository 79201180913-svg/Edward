from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


CONFIDENCE_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    strategy_confidence: float
    forecast_confidence: float
    regime_confidence: float
    portfolio_confidence: float
    overall_confidence: float
    level: str
    version: str = CONFIDENCE_VERSION


class ConfidenceService:
    """Combine independent evidence-quality components into calibrated confidence."""

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def calculate(
        cls,
        *,
        strategy_quality: float,
        forecast_quality: float,
        regime_confidence: float,
        portfolio_confidence: float,
        uncertainty_width_pct: Optional[float] = None,
    ) -> ConfidenceResult:
        components = [
            cls._clamp(strategy_quality),
            cls._clamp(forecast_quality),
            cls._clamp(regime_confidence),
            cls._clamp(portfolio_confidence),
        ]
        overall = (
            components[0] * 0.35
            + components[1] * 0.30
            + components[2] * 0.15
            + components[3] * 0.20
        )
        if uncertainty_width_pct is not None:
            penalty = min(30.0, max(0.0, float(uncertainty_width_pct)) * 0.5)
            overall -= penalty
        overall = cls._clamp(overall)
        level = "High" if overall >= 75.0 else "Medium" if overall >= 55.0 else "Low"
        return ConfidenceResult(*components, round(overall, 4), level)


__all__ = ["CONFIDENCE_VERSION", "ConfidenceResult", "ConfidenceService"]
