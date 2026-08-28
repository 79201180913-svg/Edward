from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from edward.services.entry_quality_service_v082 import EntryQualityResult, EntryQualityServiceV082


@dataclass(frozen=True, slots=True)
class EntryQualityIntegrationResult:
    entry_quality: EntryQualityResult
    opportunity_supported: bool
    reason_codes: tuple[str, ...] = ()


class EntryQualityIntegrationServiceV082:
    """Thin integration boundary between analysis factors and entry quality.

    It intentionally does not make the final BUY/SELL decision. The existing
    opportunity/decision layers remain authoritative for execution decisions.
    """

    @staticmethod
    def _value(source: Any, *names: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            for name in names:
                if name in source:
                    return source[name]
            return default
        for name in names:
            if hasattr(source, name):
                return getattr(source, name)
        return default

    @classmethod
    def evaluate(cls, *, fundamental: Any = None, market: Any = None, profile: str = "medium_term", execution_allowed: bool = True) -> EntryQualityIntegrationResult:
        fundamental_score = cls._value(fundamental, "overall_score", "score")
        momentum_group = cls._value(fundamental, "fundamental_momentum", default=None)
        momentum_score = cls._value(momentum_group, "score")
        regime = cls._value(market, "regime", "market_regime")
        regime_score = cls._value(market, "regime_score", "score")
        signal = cls._value(market, "current_signal", "signal", "direction")
        micro = cls._value(market, "microstructure_score", "microstructure")
        volume = cls._value(market, "volume_pressure_score", "volume_pressure")
        result = EntryQualityServiceV082.evaluate(
            fundamental_score=fundamental_score,
            fundamental_momentum_score=momentum_score,
            regime=regime,
            regime_score=regime_score,
            current_signal=signal,
            microstructure_score=micro,
            volume_pressure_score=volume,
            profile=profile,
            execution_allowed=execution_allowed,
        )
        reasons = () if not result.entry_blocked else (result.block_reason or "ENTRY_BLOCKED",)
        return EntryQualityIntegrationResult(result, result.entry_signal, reasons)


__all__ = ["EntryQualityIntegrationResult", "EntryQualityIntegrationServiceV082"]
