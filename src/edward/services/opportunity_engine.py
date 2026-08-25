from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.analysis_service import AnalysisService, AnalysisResult, StrategyResult
from edward.services.decision_engine import OpportunityContext
from edward.services.risk_engine import RiskEngine, RiskResult


@dataclass(frozen=True, slots=True)
class OpportunityResult:
    context: OpportunityContext
    score: float
    entry_signal: bool
    market_regime_compatible: bool
    explanation: str
    risk: RiskResult | None = None


class OpportunityEngine:
    """Current opportunity layer combining strategy, entry, market, risk and portfolio fit."""

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
        *,
        position_weight_pct: float = 0.0,
        target_weight_pct: float = 0.0,
        max_position_weight_pct: float | None = None,
        portfolio_available: bool = True,
        available_cash: float | None = None,
        estimated_trade_value: float | None = None,
    ) -> OpportunityResult:
        if strategy_result is None:
            context = OpportunityContext(
                opportunity_score=0.0,
                entry_ok=False,
                risk_ok=False,
                strategy_ok=False,
                market_regime_compatible=False,
                critical_risk=True,
            )
            return OpportunityResult(context, 0.0, False, False, "Приемлемая стратегия отсутствует.", None)

        risk = RiskEngine.evaluate(
            strategy_result=strategy_result,
            candles=candles,
            profile=analysis.profile,
            position_weight_pct=position_weight_pct,
            target_weight_pct=target_weight_pct,
            max_position_weight_pct=max_position_weight_pct,
            portfolio_available=portfolio_available,
            available_cash=available_cash,
            estimated_trade_value=estimated_trade_value,
        )

        if not strategy_result.quality_gate:
            context = OpportunityContext(
                opportunity_score=0.0,
                entry_ok=False,
                risk_ok=risk.gate,
                strategy_ok=False,
                market_regime_compatible=False,
                critical_risk=risk.critical,
            )
            return OpportunityResult(context, 0.0, False, False, "Стратегия не прошла Quality Gate.", risk)

        entry_signal = AnalysisService._signal(
            strategy_result.strategy,
            candles,
            strategy_result.parameters,
            len(candles) - 1,
        )
        market_ok = cls._market_compatible(analysis.market_regime, strategy_result.strategy)
        entry_score = 100.0 if entry_signal else 35.0
        market_score = 100.0 if market_ok else 35.0
        strategy_score = min(100.0, max(0.0, strategy_result.score))
        confidence_score = {"High": 100.0, "Medium": 70.0, "Low": 40.0}.get(analysis.confidence, 40.0)
        portfolio_fit = risk.portfolio_fit_score
        score = round(
            strategy_score * 0.30
            + entry_score * 0.20
            + market_score * 0.15
            + risk.score * 0.20
            + portfolio_fit * 0.10
            + confidence_score * 0.05,
            2,
        )
        context = OpportunityContext(
            opportunity_score=score,
            entry_ok=entry_signal,
            risk_ok=risk.gate,
            strategy_ok=True,
            market_regime_compatible=market_ok,
            critical_risk=risk.critical,
        )
        explanation = (
            f"Strategy={strategy_score:.1f}, entry={entry_score:.0f}, market={market_score:.0f}, "
            f"risk={risk.score:.1f}, portfolio={portfolio_fit:.1f}, confidence={confidence_score:.0f}."
        )
        return OpportunityResult(context, score, entry_signal, market_ok, explanation, risk)
