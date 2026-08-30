from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from edward.services.regime_engine_v08 import RegimeResult, RegimeEngine

logger = logging.getLogger(__name__)


STRATEGY_ROUTER_V084_VERSION = "0.8.4"


@dataclass(frozen=True, slots=True)
class StrategyRoutingDecision:
    strategy: str
    regime: str
    compatibility: float
    priority: str
    eligible: bool
    evidence_multiplier: float
    reason: str


@dataclass(frozen=True, slots=True)
class StrategyRoutingResult:
    regime: str
    regime_confidence: float
    decisions: tuple[StrategyRoutingDecision, ...]
    ordered_strategies: tuple[str, ...]


class StrategyRouterV084:
    """Rank strategy families against the current regime without hard disabling them.

    Routing is a prioritization/evidence policy. It does not replace WF, OOS or
    Quality Gate decisions and never uses OOS data.
    """

    STRATEGIES = ("Trend Following", "Momentum", "Breakout", "Mean Reversion")

    _HIGH = 80.0
    _MEDIUM = 60.0
    _TRANSITION_MULTIPLIER = 0.85
    _UNKNOWN_MULTIPLIER = 0.70

    @classmethod
    def _priority(cls, compatibility: float, regime: str) -> str:
        if compatibility >= cls._HIGH:
            priority = "HIGH"
        elif compatibility >= cls._MEDIUM:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        if regime == "TRANSITION" and priority == "HIGH":
            return "MEDIUM"
        return priority

    @classmethod
    def _multiplier(cls, regime: str, compatibility: float) -> float:
        base = max(0.50, min(1.0, compatibility / 100.0))
        if regime == "TRANSITION":
            base *= cls._TRANSITION_MULTIPLIER
        elif regime == "UNKNOWN":
            base *= cls._UNKNOWN_MULTIPLIER
        return round(base, 4)

    @classmethod
    def route(
        cls,
        regime_result: RegimeResult,
        strategies: Sequence[str] | None = None,
        *,
        ticker: str | None = None,
    ) -> StrategyRoutingResult:
        names = tuple(strategies or cls.STRATEGIES)
        logger.warning(
            "[V084 ROUTER START] ticker=%s regime=%s confidence=%.2f trend_score=%.4f volatility_pct=%.4f volatility_percentile=%.2f strategies=%s",
            ticker, regime_result.regime, regime_result.confidence, regime_result.trend_score,
            regime_result.volatility_pct, regime_result.volatility_percentile, names,
        )
        decisions: list[StrategyRoutingDecision] = []
        for strategy in names:
            compatibility = RegimeEngine.compatibility(regime_result.regime, strategy)
            priority = cls._priority(compatibility, regime_result.regime)
            multiplier = cls._multiplier(regime_result.regime, compatibility)
            eligible = regime_result.regime != "UNKNOWN" and compatibility > 0.0
            if regime_result.regime == "TRANSITION":
                reason = "transition regime: conservative evidence multiplier"
            elif regime_result.regime == "UNKNOWN":
                reason = "unknown regime: reduced confidence; routing is diagnostic only"
            elif priority == "HIGH":
                reason = "strong regime compatibility"
            elif priority == "MEDIUM":
                reason = "moderate regime compatibility"
            else:
                reason = "weak regime compatibility"
            decision = StrategyRoutingDecision(
                strategy=strategy,
                regime=regime_result.regime,
                compatibility=round(compatibility, 2),
                priority=priority,
                eligible=eligible,
                evidence_multiplier=multiplier,
                reason=reason,
            )
            decisions.append(decision)
            logger.warning(
                "[V084 ROUTER STRATEGY] ticker=%s strategy=%s regime=%s compatibility=%.2f priority=%s eligible=%s evidence_multiplier=%.4f reason=%s",
                ticker, strategy, regime_result.regime, compatibility, priority, eligible, multiplier, reason,
            )
        ordered = tuple(item.strategy for item in sorted(decisions, key=lambda item: (-item.compatibility, item.strategy)))
        logger.warning(
            "[V084 ROUTER RESULT] ticker=%s regime=%s ordered_strategies=%s transition_policy=%s",
            ticker, regime_result.regime, ordered, regime_result.regime == "TRANSITION",
        )
        return StrategyRoutingResult(
            regime=regime_result.regime,
            regime_confidence=regime_result.confidence,
            decisions=tuple(decisions),
            ordered_strategies=ordered,
        )


__all__ = ["STRATEGY_ROUTER_V084_VERSION", "StrategyRoutingDecision", "StrategyRoutingResult", "StrategyRouterV084"]
