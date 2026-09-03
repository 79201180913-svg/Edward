from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import pstdev
from typing import Any

from edward.services.analysis_service import AnalysisService, StrategyResult


@dataclass(frozen=True, slots=True)
class RiskResult:
    score: float
    level: str
    gate: bool
    critical: bool
    volatility_pct: float
    max_drawdown_pct: float
    position_weight_pct: float
    target_weight_pct: float
    portfolio_fit_score: float
    reasons: tuple[str, ...]


class RiskEngine:
    """Risk assessment with hard admissibility limits and descriptive scoring."""

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _annualized_volatility(candles: list[Any]) -> float:
        returns: list[float] = []
        for previous, current in zip(candles, candles[1:]):
            previous_close = float(getattr(previous, "close", 0.0) or 0.0)
            current_close = float(getattr(current, "close", 0.0) or 0.0)
            if previous_close:
                returns.append(current_close / previous_close - 1.0)
        if len(returns) < 2:
            return 0.0
        return pstdev(returns) * sqrt(252.0) * 100.0

    @classmethod
    def evaluate(
        cls,
        *,
        strategy_result: StrategyResult | None,
        candles: list[Any],
        profile: str,
        position_weight_pct: float = 0.0,
        target_weight_pct: float = 0.0,
        max_position_weight_pct: float | None = None,
        portfolio_available: bool = True,
        available_cash: float | None = None,
        estimated_trade_value: float | None = None,
    ) -> RiskResult:
        if strategy_result is None:
            return RiskResult(0.0, "HIGH", False, True, 0.0, 0.0, position_weight_pct, target_weight_pct, 0.0, ("STRATEGY_UNAVAILABLE",))

        cfg = AnalysisService._profile_params(profile)
        volatility_pct = cls._annualized_volatility(candles)
        max_dd = float(strategy_result.max_drawdown_pct)
        dd_limit = float(cfg["max_drawdown_pct"])
        volatility_limit = {"long_term": 45.0, "medium_term": 60.0, "speculative": 90.0}[profile]
        max_weight = max_position_weight_pct if max_position_weight_pct is not None else float(target_weight_pct or 10.0) * 1.5

        reasons: list[str] = []
        dd_score = cls._clamp((1.0 - max_dd / max(dd_limit, 0.01)) * 100.0)
        vol_score = cls._clamp((1.0 - volatility_pct / volatility_limit) * 100.0)
        sharpe_score = cls._clamp((float(strategy_result.sharpe) + 1.0) / 2.0 * 100.0)
        weight_score = 100.0
        if max_weight > 0:
            weight_score = cls._clamp((1.0 - max(0.0, position_weight_pct - target_weight_pct) / max_weight) * 100.0)
        cash_score = 100.0
        if estimated_trade_value is not None and available_cash is not None:
            cash_score = 100.0 if estimated_trade_value <= max(0.0, available_cash) else 0.0

        portfolio_fit = cls._clamp(min(weight_score, cash_score) if portfolio_available else 0.0)
        score = round(
            dd_score * 0.30
            + vol_score * 0.25
            + sharpe_score * 0.20
            + portfolio_fit * 0.25,
            2,
        )

        if max_dd > dd_limit:
            reasons.append("MAX_DRAWDOWN_LIMIT")
        if volatility_pct > volatility_limit:
            reasons.append("VOLATILITY_HIGH")
        if position_weight_pct > max_weight:
            reasons.append("POSITION_WEIGHT_LIMIT")
        if not portfolio_available:
            reasons.append("PORTFOLIO_CONTEXT_UNAVAILABLE")
        if cash_score < 100.0:
            reasons.append("INSUFFICIENT_CASH")

        # V815-06: every hard admissibility-limit breach is critical. The
        # descriptive score never overrides this flag or the hard gate.
        critical = bool(reasons)
        gate = not critical
        level = "LOW" if score >= 75 and not critical else "MEDIUM" if score >= 50 and not critical else "HIGH"

        return RiskResult(
            score=score,
            level=level,
            gate=gate,
            critical=critical,
            volatility_pct=round(volatility_pct, 2),
            max_drawdown_pct=round(max_dd, 2),
            position_weight_pct=round(position_weight_pct, 2),
            target_weight_pct=round(target_weight_pct, 2),
            portfolio_fit_score=round(portfolio_fit, 2),
            reasons=tuple(reasons),
        )
