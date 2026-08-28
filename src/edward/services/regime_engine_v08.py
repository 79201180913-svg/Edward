from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Any, Sequence

from edward.services.analysis_service import Candle


REGIME_ENGINE_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class RegimeResult:
    regime: str
    trend_score: float
    volatility_pct: float
    volatility_percentile: float
    confidence: float
    version: str = REGIME_ENGINE_VERSION


@dataclass(frozen=True, slots=True)
class RegimePerformance:
    regime: str
    observations: int
    mean_return_pct: float
    median_return_pct: float
    win_rate_pct: float
    mean_drawdown_pct: float


class RegimeEngine:
    """Classify the current market regime and summarize strategy behavior by regime."""

    REGIMES = ("TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "LOW_VOLATILITY", "TRANSITION", "UNKNOWN")

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return [current.close / previous.close - 1.0 for previous, current in zip(candles, candles[1:]) if previous.close > 0 and current.close > 0]

    @classmethod
    def classify(cls, candles: Sequence[Candle], *, trend_window: int = 20, baseline_window: int = 50, volatility_window: int = 20) -> RegimeResult:
        if len(candles) < max(trend_window, baseline_window, volatility_window) + 1:
            return RegimeResult("UNKNOWN", 0.0, 0.0, 0.0, 0.0)
        closes = [float(c.close) for c in candles]
        fast = mean(closes[-trend_window:])
        slow = mean(closes[-baseline_window:])
        trend_score = (fast / slow - 1.0) * 100.0 if slow else 0.0
        returns = cls._returns(candles)
        recent_returns = returns[-volatility_window:]
        volatility_pct = pstdev(recent_returns) * 100.0 if len(recent_returns) > 1 else 0.0
        history_vol = [pstdev(returns[i - volatility_window:i]) * 100.0 for i in range(volatility_window, len(returns) + 1)] if len(returns) >= volatility_window + 1 else []
        percentile = sum(value <= volatility_pct for value in history_vol) / len(history_vol) * 100.0 if history_vol else 50.0

        if abs(trend_score) >= 1.0:
            regime = "TREND_UP" if trend_score > 0 else "TREND_DOWN"
        elif percentile >= 80.0:
            regime = "HIGH_VOLATILITY"
        elif percentile <= 20.0:
            regime = "LOW_VOLATILITY"
        elif abs(trend_score) <= 0.35:
            regime = "RANGE"
        else:
            regime = "TRANSITION"

        confidence = min(100.0, abs(trend_score) * 40.0 + abs(percentile - 50.0))
        if regime == "RANGE":
            confidence = min(100.0, 100.0 - abs(trend_score) * 80.0 + max(0.0, 20.0 - percentile * 0.2))
        return RegimeResult(regime, round(trend_score, 4), round(volatility_pct, 4), round(percentile, 2), round(max(0.0, confidence), 2))

    @classmethod
    def compatibility(cls, regime: str, strategy: str) -> float:
        table = {
            "TREND_UP": {"Trend Following": 100.0, "Breakout": 95.0, "Momentum": 90.0, "Mean Reversion": 20.0},
            "TREND_DOWN": {"Trend Following": 85.0, "Breakout": 75.0, "Momentum": 70.0, "Mean Reversion": 15.0},
            "RANGE": {"Trend Following": 25.0, "Breakout": 35.0, "Momentum": 30.0, "Mean Reversion": 100.0},
            "HIGH_VOLATILITY": {"Trend Following": 70.0, "Breakout": 80.0, "Momentum": 75.0, "Mean Reversion": 35.0},
            "LOW_VOLATILITY": {"Trend Following": 55.0, "Breakout": 45.0, "Momentum": 50.0, "Mean Reversion": 70.0},
            "TRANSITION": {"Trend Following": 45.0, "Breakout": 50.0, "Momentum": 45.0, "Mean Reversion": 45.0},
            "UNKNOWN": {"Trend Following": 0.0, "Breakout": 0.0, "Momentum": 0.0, "Mean Reversion": 0.0},
        }
        return table.get(regime, {}).get(strategy, 0.0)

    @staticmethod
    def summarize_performance(regime: str, returns_pct: Sequence[float], drawdowns_pct: Sequence[float]) -> RegimePerformance:
        if not returns_pct:
            return RegimePerformance(regime, 0, 0.0, 0.0, 0.0, 0.0)
        wins = sum(value > 0 for value in returns_pct)
        return RegimePerformance(regime, len(returns_pct), mean(returns_pct), median(returns_pct), wins / len(returns_pct) * 100.0, mean(drawdowns_pct) if drawdowns_pct else 0.0)
