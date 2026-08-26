from __future__ import annotations

from typing import Any


def strategy_quality_label(quality_gate: bool | None) -> str:
    if quality_gate is None:
        return "N/A"
    return "PASS" if quality_gate else "FAIL"


def strategy_confidence_label(confidence: str | None) -> str:
    value = str(confidence or "N/A").strip()
    return value if value in {"N/A", "Low", "Medium", "High"} else "N/A"


def forecast_confidence_label(confidence: str | None) -> str:
    value = str(confidence or "N/A").strip()
    return value if value in {"N/A", "Low", "Medium", "High"} else "N/A"


def confidence_detail(*, quality_gate: bool | None, strategy_confidence: str | None, forecast_confidence: str | None) -> str:
    return "\n".join(
        (
            f"Качество стратегии: {strategy_quality_label(quality_gate)}",
            f"Уверенность стратегии: {strategy_confidence_label(strategy_confidence)}",
            f"Уверенность прогноза: {forecast_confidence_label(forecast_confidence)}",
        )
    )


def opportunity_strategy_confidence(result: Any) -> str:
    """Use the current backend contract: N/A means strategy Quality Gate failed."""
    confidence = str(getattr(result, "strategy_confidence", "") or "").strip()
    if confidence in {"Low", "Medium", "High"}:
        return confidence
    reason = str(getattr(result, "reason", "") or "").upper()
    if "STRATEGY_QUALITY_FAIL" in reason or "STRATEGY_QUALITY_DEGRADED" in reason:
        return "N/A"
    return "N/A"


__all__ = [
    "confidence_detail",
    "forecast_confidence_label",
    "opportunity_strategy_confidence",
    "strategy_confidence_label",
    "strategy_quality_label",
]
