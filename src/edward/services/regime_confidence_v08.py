from __future__ import annotations


def cap_regime_confidence(value: float, *, maximum: float = 85.0) -> float:
    """Keep regime confidence informative without implying certainty."""
    return round(max(0.0, min(float(maximum), float(value))), 2)


__all__ = ["cap_regime_confidence"]
