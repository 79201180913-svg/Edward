from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.market_volatility_context_v011 import MarketVolatilityContextAnalyzerV011


def _series(values):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(days=i), v, v, v, v, 1000) for i, v in enumerate(values)]


def test_high_relative_volatility_is_detected():
    result = MarketVolatilityContextAnalyzerV011().analyze(
        instrument_candles=_series([100, 101, 99, 101, 99, 101]),
        market_candles=_series([100, 100.2, 99.9, 100.1, 99.8, 100.0]),
        as_of=datetime(2026, 1, 6, tzinfo=timezone.utc),
        horizon_bars=5,
    )
    assert result.relative_volatility is not None
    assert result.relative_volatility > 1.25
    assert result.classification == "HIGHER_THAN_MARKET"


def test_future_candles_are_ignored():
    result = MarketVolatilityContextAnalyzerV011().analyze(
        instrument_candles=_series([100, 110, 100, 110]),
        market_candles=_series([100, 101, 100, 101]),
        as_of=datetime(2026, 1, 3, tzinfo=timezone.utc),
        horizon_bars=2,
    )
    expected = MarketVolatilityContextAnalyzerV011().analyze(
        instrument_candles=_series([100, 110, 100]),
        market_candles=_series([100, 101, 100]),
        as_of=datetime(2026, 1, 3, tzinfo=timezone.utc),
        horizon_bars=2,
    )
    assert result.instrument_volatility_pct == pytest.approx(expected.instrument_volatility_pct)
    assert result.market_volatility_pct == pytest.approx(expected.market_volatility_pct)


def test_insufficient_history_is_explicitly_unavailable():
    result = MarketVolatilityContextAnalyzerV011().analyze(
        instrument_candles=_series([100, 101]),
        market_candles=_series([100, 101]),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
        horizon_bars=2,
    )
    assert result.classification == "UNAVAILABLE"
    assert result.relative_volatility is None
