from __future__ import annotations

from typing import Literal


StrategyConfidence = Literal["N/A", "Low", "Medium", "High"]


class StrategyConfidencePolicy:
    """Business rule for strategy confidence.

    Quality Gate determines whether a strategy is eligible. Confidence is only
    meaningful for a strategy that passed the gate. Forecast confidence is a
    separate concern and must not be normalized by this policy.
    """

    NA: StrategyConfidence = "N/A"

    @classmethod
    def resolve(cls, *, quality_gate: bool, confidence: str | None) -> StrategyConfidence:
        if not quality_gate:
            return cls.NA
        value = str(confidence or "").strip()
        if value in {"Low", "Medium", "High"}:
            return value  # type: ignore[return-value]
        return "Low"

    @classmethod
    def validate(cls, *, quality_gate: bool, confidence: str | None) -> None:
        resolved = cls.resolve(quality_gate=quality_gate, confidence=confidence)
        if not quality_gate and resolved != cls.NA:
            raise ValueError("Strategy confidence must be N/A when Quality Gate fails")
        if quality_gate and resolved == cls.NA:
            raise ValueError("Strategy confidence cannot be N/A when Quality Gate passes")
