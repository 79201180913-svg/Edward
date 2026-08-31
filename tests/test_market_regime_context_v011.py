from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.market_regime_context_v011 import MarketRegimeContextBuilderV011


def _candles(count: int = 60):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(days=i), 100 + i, 101 + i, 99 + i, 100 + i, 1000)
        for i in range(count)
    ]


def test_context_is_point_in_time():
    candles = _candles()
    cutoff = candles[49].timestamp
    context = MarketRegimeContextBuilderV011().build("TEST", cutoff, candles)
    assert context.source_candles == 50
    assert context.result.regime in {"TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "LOW_VOLATILITY", "TRANSITION", "UNKNOWN"}


def test_context_excludes_future_candles():
    candles = _candles()
    cutoff = candles[30].timestamp
    context = MarketRegimeContextBuilderV011().build("TEST", cutoff, candles)
    assert context.source_candles == 31


def test_context_uses_canonical_engine_result():
    candles = _candles()
    cutoff = candles[-1].timestamp
    context = MarketRegimeContextBuilderV011().build("TEST", cutoff, candles)
    assert context.result.version == "0.8.0"
    assert set(context.result.strategy_compatibility) == {
        "Trend Following", "Momentum", "Breakout", "Mean Reversion"
    }
