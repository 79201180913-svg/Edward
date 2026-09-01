from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from edward.domain import TradingPathAnalysisV012
from edward.services.analysis_service import Candle, StrategyResult
from edward.services.risk_engine import RiskEngine, RiskResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TradingPathRiskResultV012:
    risk: RiskResult
    path_eligible: bool
    reason: str | None = None


class TradingPathRiskServiceV012:
    """Evaluate risk for a concrete path using the existing RiskEngine.

    The adapter deliberately does not invent path-specific risk math. Until the
    path has a compatible StrategyResult projection, callers must supply one.
    This keeps risk semantics identical to the existing platform while making
    path eligibility explicit.
    """

    @classmethod
    def evaluate(
        cls,
        analysis: TradingPathAnalysisV012,
        *,
        candles: Sequence[Candle],
        strategy_result: StrategyResult | None,
        profile: str,
        position_weight_pct: float = 0.0,
        target_weight_pct: float = 0.0,
        max_position_weight_pct: float | None = None,
        portfolio_available: bool = True,
        available_cash: float | None = None,
        estimated_trade_value: float | None = None,
    ) -> TradingPathRiskResultV012:
        risk = RiskEngine.evaluate(
            strategy_result=strategy_result,
            candles=list(candles),
            profile=profile,
            position_weight_pct=position_weight_pct,
            target_weight_pct=target_weight_pct,
            max_position_weight_pct=max_position_weight_pct,
            portfolio_available=portfolio_available,
            available_cash=available_cash,
            estimated_trade_value=estimated_trade_value,
        )
        eligible = bool(risk.gate and not risk.critical)
        reason = None if eligible else ",".join(risk.reasons) or "RISK_GATE_FAILED"
        logger.warning(
            "[V012 PATH RISK] ticker=%s hypothesis=%s score=%.2f gate=%s critical=%s eligible=%s reason=%s",
            analysis.ticker,
            analysis.hypothesis,
            risk.score,
            risk.gate,
            risk.critical,
            eligible,
            reason or "none",
        )
        return TradingPathRiskResultV012(risk=risk, path_eligible=eligible, reason=reason)


__all__ = ["TradingPathRiskResultV012", "TradingPathRiskServiceV012"]
