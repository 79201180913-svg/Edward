from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from edward.services.research_backtest_service_v08 import ResearchBacktestResult

ECONOMIC_VIABILITY_V084_VERSION = "0.8.4"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EconomicViabilityResultV084:
    """Train-only admissibility decision for a parameter candidate."""

    eligible: bool
    reasons: tuple[str, ...]
    min_excess_return_pct: float
    max_drawdown_pct: float | None
    min_trades: int


class EconomicViabilityServiceV084:
    """Reject economically invalid Train candidates before robust ranking.

    This service is deliberately Train-only. It never consumes OOS evidence.
    """

    NEGATIVE_EXCESS_RETURN = "NEGATIVE_EXCESS_RETURN"
    EXCESSIVE_DRAWDOWN = "EXCESSIVE_DRAWDOWN"
    INSUFFICIENT_TRADES = "INSUFFICIENT_TRADES"
    INSUFFICIENT_RETURN = "INSUFFICIENT_RETURN"

    @classmethod
    def evaluate(
        cls,
        result: ResearchBacktestResult,
        *,
        min_excess_return_pct: float = 0.0,
        max_drawdown_pct: float | None = None,
        min_trades: int = 1,
        min_net_return_pct: float | None = None,
    ) -> EconomicViabilityResultV084:
        reasons: list[str] = []
        if result.excess_return_pct <= min_excess_return_pct:
            reasons.append(cls.NEGATIVE_EXCESS_RETURN)
        if max_drawdown_pct is not None and result.max_drawdown_pct > max_drawdown_pct:
            reasons.append(cls.EXCESSIVE_DRAWDOWN)
        if result.trades < min_trades:
            reasons.append(cls.INSUFFICIENT_TRADES)
        if min_net_return_pct is not None and result.net_return_pct <= min_net_return_pct:
            reasons.append(cls.INSUFFICIENT_RETURN)

        decision = EconomicViabilityResultV084(
            eligible=not reasons,
            reasons=tuple(reasons),
            min_excess_return_pct=min_excess_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            min_trades=min_trades,
        )
        logger.warning(
            "[V084 WF VIABILITY] eligible=%s reasons=%s excess=%.4f net_return=%.4f dd=%.4f trades=%d thresholds={min_excess:%.4f,max_dd:%s,min_trades:%d,min_return:%s}",
            decision.eligible,
            decision.reasons,
            result.excess_return_pct,
            result.net_return_pct,
            result.max_drawdown_pct,
            result.trades,
            min_excess_return_pct,
            max_drawdown_pct,
            min_trades,
            min_net_return_pct,
        )
        return decision


__all__ = [
    "ECONOMIC_VIABILITY_V084_VERSION",
    "EconomicViabilityResultV084",
    "EconomicViabilityServiceV084",
]
