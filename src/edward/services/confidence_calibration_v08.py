from __future__ import annotations

from edward.services.confidence_service_v08 import ConfidenceResult


def calculate_confidence(
    *,
    strategy_quality: float,
    forecast_quality: float,
    regime_confidence: float,
    portfolio_confidence: float,
    observations: int,
    uncertainty_width_pct: float | None = None,
) -> ConfidenceResult:
    values = [
        max(0.0, min(100.0, float(strategy_quality))),
        max(0.0, min(100.0, float(forecast_quality))),
        max(0.0, min(100.0, float(regime_confidence))),
        max(0.0, min(100.0, float(portfolio_confidence))),
    ]
    score = values[0] * 0.35 + values[1] * 0.30 + values[2] * 0.15 + values[3] * 0.20
    if uncertainty_width_pct is not None:
        score -= min(30.0, max(0.0, float(uncertainty_width_pct)) * 0.5)
    if observations < 10:
        factor = 0.45
    elif observations < 30:
        factor = 0.65
    elif observations < 60:
        factor = 0.82
    elif observations < 100:
        factor = 0.92
    else:
        factor = 1.0
    score = max(0.0, min(100.0, score * factor))

    # Small samples cannot support Medium/High confidence, regardless of
    # component scores. This is a hard evidential ceiling, not a penalty.
    if observations < 50:
        level = "Low"
        score = min(score, 59.99)
    elif observations < 100:
        level = "High" if score >= 75.0 else "Medium" if score >= 60.0 else "Low"
    else:
        level = "High" if score >= 75.0 else "Medium" if score >= 60.0 else "Low"

    return ConfidenceResult(*values, round(score, 4), level)


__all__ = ["calculate_confidence"]
