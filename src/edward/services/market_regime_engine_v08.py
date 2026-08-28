from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Iterable, Sequence

from edward.services.analysis_service import Candle


REGIME_ENGINE_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class RegimeFeaturesV08:
    trend_strength: float
    volatility_pct: float
    distance_from_sma_pct: float
    momentum_pct: float


@dataclass(frozen=True, slots=True)
class MarketRegimeResultV08:
    regime: str
    confidence: float
    features: RegimeFeaturesV08
    strategy_compatibility: dict[str, float]
    version: str = REGIME_ENGINE_VERSION


class MarketRegimeEngineV08:
    """Deterministic regime classifier for research and decision context."""

    REGIMES = ("TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "LOW_VOLATILITY", "TRANSITION", "UNKNOWN")

    @staticmethod
    def _sma(values: Sequence[float], period: int) -> float:
        return mean(values[-period:]) if values else 0.0

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return [current.close / previous.close - 1.0 for previous, current in zip(candles, candles[1:]) if previous.close]

    @classmethod
    def features(cls, candles: Iterable[Candle]) -> RegimeFeaturesV08:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        closes = [float(item.close) for item in ordered]
        if len(closes) < 30:
            return RegimeFeaturesV08(0.0, 0.0, 0.0, 0.0)
        sma20 = cls._sma(closes, 20)
        sma50 = cls._sma(closes, min(50, len(closes)))
        returns = cls._returns(ordered[-30:])
        volatility = pstdev(returns) * sqrt(252.0) * 100.0 if len(returns) > 1 else 0.0
        trend = (sma20 / sma50 - 1.0) * 100.0 if sma50 else 0.0
        distance = (closes[-1] / sma20 - 1.0) * 100.0 if sma20 else 0.0
        lookback = min(20, len(closes) - 1)
        momentum = (closes[-1] / closes[-1 - lookback] - 1.0) * 100.0 if closes[-1 - lookback] else 0.0
        return RegimeFeaturesV08(trend_strength=trend, volatility_pct=volatility, distance_from_sma_pct=distance, momentum_pct=momentum)

    @classmethod
    def classify(cls, candles: Iterable[Candle]) -> MarketRegimeResultV08:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if len(ordered) < 50:
            features = cls.features(ordered)
            return MarketRegimeResultV08("UNKNOWN", 0.0, features, {}, cls.__name__ and REGIME_ENGINE_VERSION)

        features = cls.features(ordered)
        trend_abs = abs(features.trend_strength)
        vol = features.volatility_pct

        if vol >= 60.0:
            regime = "HIGH_VOLATILITY"
            confidence = min(100.0, 55.0 + (vol - 60.0))
        elif vol <= 15.0:
            regime = "LOW_VOLATILITY"
            confidence = min(100.0, 55.0 + (15.0 - vol))
        elif trend_abs >= 1.5 and features.distance_from_sma_pct * features.trend_strength > 0:
            regime = "TREND_UP" if features.trend_strength > 0 else "TREND_DOWN"
            confidence = min(100.0, 55.0 + trend_abs * 10.0 + abs(features.momentum_pct))
        elif trend_abs <= 0.5 and abs(features.distance_from_sma_pct) <= 1.5:
            regime = "RANGE"
            confidence = min(100.0, 55.0 + (0.5 - trend_abs) * 60.0)
        else:
            regime = "TRANSITION"
            confidence = 50.0

        confidence = round(max(0.0, min(100.0, confidence)), 2)
        compatibility = cls._compatibility(regime)
        return MarketRegimeResultV08(regime, confidence, features, compatibility)

    @staticmethod
    def _compatibility(regime: str) -> dict[str, float]:
        base = {
            "Trend Following": 0.0,
            "Momentum": 0.0,
            "Breakout": 0.0,
            "Mean Reversion": 0.0,
        }
        if regime == "TREND_UP":
            return {"Trend Following": 100.0, "Momentum": 85.0, "Breakout": 80.0, "Mean Reversion": 25.0}
        if regime == "TREND_DOWN":
            return {"Trend Following": 90.0, "Momentum": 75.0, "Breakout": 70.0, "Mean Reversion": 20.0}
        if regime == "RANGE":
            return {"Trend Following": 25.0, "Momentum": 30.0, "Breakout": 20.0, "Mean Reversion": 100.0}
        if regime == "HIGH_VOLATILITY":
            return {"Trend Following": 55.0, "Momentum": 50.0, "Breakout": 75.0, "Mean Reversion": 30.0}
        if regime == "LOW_VOLATILITY":
            return {"Trend Following": 60.0, "Momentum": 45.0, "Breakout": 35.0, "Mean Reversion": 80.0}
        if regime == "TRANSITION":
            return {"Trend Following": 35.0, "Momentum": 35.0, "Breakout": 40.0, "Mean Reversion": 35.0}
        return base


__all__ = ["REGIME_ENGINE_VERSION", "RegimeFeaturesV08", "MarketRegimeResultV08", "MarketRegimeEngineV08"]
