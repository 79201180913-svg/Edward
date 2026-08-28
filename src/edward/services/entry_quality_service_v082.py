from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _score_direction(value: Any) -> float:
    text = str(value or "").upper()
    if text in {"BUY", "LONG", "POSITIVE", "BULLISH", "UP"}:
        return 100.0
    if text in {"SELL", "SHORT", "NEGATIVE", "BEARISH", "DOWN"}:
        return 0.0
    return 50.0


@dataclass(frozen=True, slots=True)
class EntryQualityResult:
    score: float
    available: bool
    entry_signal: bool
    fundamental_support: float
    regime_alignment: float
    momentum_alignment: float
    microstructure_score: float
    volume_pressure_score: float
    signal_score: float
    entry_blocked: bool
    block_reason: str | None
    profile: str


class EntryQualityServiceV082:
    """Determines whether the current market state provides a usable entry.

    Fundamentals support an entry but cannot create one. The service is intentionally
    separate from the final BUY/SELL decision and from fundamental company quality.
    """

    PROFILE_WEIGHTS = {
        "long_term": {"fundamental": .25, "regime": .25, "momentum": .15, "microstructure": .20, "volume": .10, "signal": .05},
        "medium_term": {"fundamental": .15, "regime": .20, "momentum": .20, "microstructure": .20, "volume": .10, "signal": .15},
        "speculative": {"fundamental": .05, "regime": .15, "momentum": .25, "microstructure": .25, "volume": .15, "signal": .15},
    }
    ALIASES = {"long-term": "long_term", "longterm": "long_term", "medium-term": "medium_term", "mediumterm": "medium_term", "short-term": "speculative", "shortterm": "speculative"}

    @classmethod
    def _profile(cls, profile: str) -> str:
        normalized = str(profile or "medium_term").strip().lower().replace(" ", "_")
        return cls.ALIASES.get(normalized, normalized if normalized in cls.PROFILE_WEIGHTS else "medium_term")

    @classmethod
    def evaluate(
        cls,
        *,
        fundamental_score: float | None = None,
        fundamental_momentum_score: float | None = None,
        regime: str | None = None,
        regime_score: float | None = None,
        current_signal: Any = None,
        microstructure_score: float | None = None,
        volume_pressure_score: float | None = None,
        profile: str = "medium_term",
        execution_allowed: bool = True,
    ) -> EntryQualityResult:
        selected = cls._profile(profile)
        weights = cls.PROFILE_WEIGHTS[selected]
        signal_score = _score_direction(current_signal if not isinstance(current_signal, Mapping) else current_signal.get("direction"))
        regime_text = str(regime or "").upper()
        if regime_score is None:
            regime_score = 100.0 if regime_text in {"BULL", "BULLISH", "UPTREND", "FAVORABLE"} else 0.0 if regime_text in {"BEAR", "BEARISH", "DOWNTREND", "HOSTILE"} else 50.0
        momentum_score = fundamental_momentum_score if fundamental_momentum_score is not None else 50.0
        fundamental = fundamental_score if fundamental_score is not None else 50.0
        micro = microstructure_score if microstructure_score is not None else 50.0
        volume = volume_pressure_score if volume_pressure_score is not None else 50.0
        values = {"fundamental": _clamp(fundamental), "regime": _clamp(regime_score), "momentum": _clamp(momentum_score), "microstructure": _clamp(micro), "volume": _clamp(volume), "signal": signal_score}
        score = _clamp(sum(values[key] * weights[key] for key in weights))
        # A valid entry requires directional market confirmation. Strong fundamentals
        # are deliberately insufficient to manufacture an entry signal.
        direction_confirmed = signal_score >= 60.0
        regime_confirmed = values["regime"] >= 45.0
        entry_signal = execution_allowed and direction_confirmed and regime_confirmed and score >= 55.0
        blocked = not execution_allowed or not direction_confirmed or not regime_confirmed
        if not execution_allowed:
            reason = "EXECUTION_NOT_ALLOWED"
        elif not direction_confirmed:
            reason = "NO_BULLISH_ENTRY_SIGNAL"
        elif not regime_confirmed:
            reason = "REGIME_NOT_SUPPORTIVE"
        else:
            reason = None
        return EntryQualityResult(score, True, entry_signal, values["fundamental"], values["regime"], values["momentum"], values["microstructure"], values["volume"], values["signal"], blocked, reason, selected)


__all__ = ["EntryQualityResult", "EntryQualityServiceV082"]
