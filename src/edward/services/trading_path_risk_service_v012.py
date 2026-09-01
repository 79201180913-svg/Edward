from __future__ import annotations

import logging
from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
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
    """Evaluate path risk using existing RiskEngine semantics and path OOS evidence."""

    @staticmethod
    def _max_drawdown_pct(returns_pct: Sequence[float]) -> float:
        equity, peak, maximum = 100.0, 100.0, 0.0
        for value in returns_pct:
            equity *= 1.0 + float(value) / 100.0
            peak = max(peak, equity)
            maximum = max(maximum, (peak - equity) / peak * 100.0) if peak > 0 else maximum
        return maximum

    @staticmethod
    def _strategy_projection(analysis: TradingPathAnalysisV012, oos_windows) -> StrategyResult | None:
        returns = tuple(value for window in oos_windows for value in window.returns_pct)
        if not returns:
            return None
        average = mean(returns)
        deviation = pstdev(returns) if len(returns) > 1 else 0.0
        sharpe = average / deviation * sqrt(len(returns)) if deviation > 0 else 0.0
        positive_windows = sum(window.positive for window in oos_windows)
        return StrategyResult(
            strategy=analysis.strategy_family,
            parameters={"path_hypothesis": analysis.hypothesis},
            return_pct=average,
            max_drawdown_pct=TradingPathRiskServiceV012._max_drawdown_pct(returns),
            sharpe=sharpe,
            trades=len(returns),
            stability=positive_windows / len(oos_windows) * 100.0 if oos_windows else 0.0,
            quality_gate=False,
            score=0.0,
            test_score=average,
            wf_windows=len(oos_windows),
            positive_return_windows=positive_windows,
            positive_sharpe_windows=sum(window.excess_return_pct > 0 for window in oos_windows),
        )

    @classmethod
    def evaluate(
        cls,
        analysis: TradingPathAnalysisV012,
        *,
        candles: Sequence[Candle],
        profile: str,
        oos_windows=(),
        strategy_result: StrategyResult | None = None,
        position_weight_pct: float = 0.0,
        target_weight_pct: float = 0.0,
        max_position_weight_pct: float | None = None,
        portfolio_available: bool = True,
        available_cash: float | None = None,
        estimated_trade_value: float | None = None,
    ) -> TradingPathRiskResultV012:
        projected = strategy_result or cls._strategy_projection(analysis, oos_windows)
        risk = RiskEngine.evaluate(
            strategy_result=projected,
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
            analysis.ticker, analysis.hypothesis, risk.score, risk.gate, risk.critical, eligible, reason or "none",
        )
        return TradingPathRiskResultV012(risk=risk, path_eligible=eligible, reason=reason)


__all__ = ["TradingPathRiskResultV012", "TradingPathRiskServiceV012"]
