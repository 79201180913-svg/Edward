from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.analysis_service import AnalysisService, AnalysisResult, StrategyResult
from edward.services.decision_engine import OpportunityContext


@dataclass(frozen=True, slots=True)
class OpportunityResult:
    context: OpportunityContext
    score: float
    entry_signal: bool
    market_regime_compatible: bool
    explanation: str


class OpportunityEngine:
    """Beta current-opportunity layer between strategy analysis and decisions.

    Historical Strategy Score remains separate from current Opportunity Score.
    Risk is a gate; the score itself reflects strategy quality, entry readiness,
    and market-regime compatibility.
    """

    @staticmethod
    def _market_compatible(regime: str, strategy: str) -> bool:
        mapping = {
            "Trend": {"Trend Following", "Breakout"},
            "Momentum": {"Momentum", "Trend Following"},
            "Range": {"Mean Reversion"},
            "Unclear": set(),
        }
        return strategy in mapping.get(regime, set())

    @classmethod
    def evaluate(
        cls,
        analysis: AnalysisResult,
        candles: list[Any],
        strategy_result: StrategyResult | None,
    ) -> OpportunityResult:
        if strategy_result is None or not strategy_result.quality_gate:
            context = OpportunityContext(
                opportunity_score=0.0,
                entry_ok=False,
                risk_ok=True,
                strategy_ok=False,
                market_regime_compatible=False,
                critical_risk=False,
            )
            return OpportunityResult(
                context=context,
                score=0.0,
                entry_signal=False,
                market_regime_compatible=False,
                explanation="Приемлемая стратегия не прошла Quality Gate.",
            )

        entry_signal = AnalysisService._signal(
            strategy_result.strategy,
            candles,
            strategy_result.parameters,
            len(candles) - 1,
        )
        market_ok = cls._market_compatible(analysis.market_regime, strategy_result.strategy)
        profile = AnalysisService._profile_params(analysis.profile)
        risk_ok = (
            strategy_result.max_drawdown_pct <= profile["max_drawdown_pct"]
            and strategy_result.sharpe > 0.0
        )

        entry_score = 100.0 if entry_signal else 35.0
        market_score = 100.0 if market_ok else 35.0
        score = round(
            strategy_result.score * 0.60
            + entry_score * 0.25
            + market_score * 0.15,
            2,
        )
        context = OpportunityContext(
            opportunity_score=score,
            entry_ok=entry_signal,
            risk_ok=risk_ok,
            strategy_ok=True,
            market_regime_compatible=market_ok,
            critical_risk=not risk_ok,
        )
        return OpportunityResult(
            context=context,
            score=score,
            entry_signal=entry_signal,
            market_regime_compatible=market_ok,
            explanation=(
                f"Entry={'PASS' if entry_signal else 'WAIT'}, "
                f"market={'PASS' if market_ok else 'WAIT'}, "
                f"risk={'PASS' if risk_ok else 'FAIL'}."
            ),
        )
