from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from edward.services.market_regime_context_v011 import MarketRegimeContextV011
from edward.services.relative_strength_analyzer_v011 import RelativeStrengthResultV011
from edward.services.market_volatility_context_v011 import VolatilityContextResultV011


MARKET_CONTEXT_SNAPSHOT_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class MarketContextSnapshotV011:
    """Immutable point-in-time market context for one instrument observation."""

    instrument_id: str
    as_of: datetime
    benchmark_id: str | None
    benchmark_supported: bool
    market_regime: MarketRegimeContextV011 | None
    relative_strength: RelativeStrengthResultV011 | None
    volatility: VolatilityContextResultV011 | None
    context_status: str
    version: str = MARKET_CONTEXT_SNAPSHOT_VERSION

    def validate_point_in_time(self) -> bool:
        """Return False if any nested context claims a timestamp after ``as_of``."""
        if self.market_regime is not None and self.market_regime.as_of > self.as_of:
            return False
        if self.relative_strength is not None and self.relative_strength.as_of > self.as_of:
            return False
        if self.volatility is not None and self.volatility.as_of > self.as_of:
            return False
        return True


def resolve_context_status(
    *,
    benchmark_supported: bool,
    market_regime: MarketRegimeContextV011 | None,
    relative_strength: RelativeStrengthResultV011 | None,
    volatility: VolatilityContextResultV011 | None,
) -> str:
    if not benchmark_supported:
        return "UNAVAILABLE"
    available = [market_regime is not None, relative_strength is not None, volatility is not None]
    if all(available):
        return "FULL"
    if any(available):
        return "PARTIAL"
    return "UNAVAILABLE"


__all__ = ["MARKET_CONTEXT_SNAPSHOT_VERSION", "MarketContextSnapshotV011", "resolve_context_status"]
