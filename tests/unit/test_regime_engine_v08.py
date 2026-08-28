from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.regime_engine_v08 import RegimeEngine


def _candles(values: list[float]) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(days=i), v, v, v, v) for i, v in enumerate(values)]


def test_uptrend_is_detected():
    values = [100.0 + i * 0.5 for i in range(100)]
    result = RegimeEngine.classify(_candles(values))
    assert result.regime == "TREND_UP"
    assert result.confidence > 0


def test_downtrend_is_detected():
    values = [150.0 - i * 0.5 for i in range(100)]
    result = RegimeEngine.classify(_candles(values))
    assert result.regime == "TREND_DOWN"


def test_unknown_when_history_is_insufficient():
    result = RegimeEngine.classify(_candles([100.0] * 10))
    assert result.regime == "UNKNOWN"


def test_strategy_compatibility_is_explicit():
    assert RegimeEngine.compatibility("TREND_UP", "Trend Following") == 100.0
    assert RegimeEngine.compatibility("RANGE", "Mean Reversion") == 100.0
    assert RegimeEngine.compatibility("UNKNOWN", "Momentum") == 0.0
