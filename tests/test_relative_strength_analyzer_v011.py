from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.relative_strength_analyzer_v011 import RelativeStrengthAnalyzerV011


def _series(values):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(days=i), v, v, v, v, 1000) for i, v in enumerate(values)]


def test_instrument_outperforms_market():
    result = RelativeStrengthAnalyzerV011().analyze(
        instrument_candles=_series([100, 102, 104, 110]),
        market_candles=_series([100, 101, 102, 104]),
        as_of=datetime(2026, 1, 4, tzinfo=timezone.utc),
        horizon_bars=2,
    )
    assert result.instrument_return_pct == pytest.approx(5.76923077)
    assert result.market_return_pct == pytest.approx(2.97029703)
    assert result.excess_return_pct == pytest.approx(2.79893374)
    assert result.classification == "OUTPERFORMING"


def test_instrument_underperforms_market():
    result = RelativeStrengthAnalyzerV011().analyze(
        instrument_candles=_series([100, 101, 102, 103]),
        market_candles=_series([100, 103, 106, 110]),
        as_of=datetime(2026, 1, 4, tzinfo=timezone.utc),
        horizon_bars=2,
    )
    assert result.classification == "UNDERPERFORMING"
    assert result.excess_return_pct < 0


def test_future_candles_are_ignored():
    result = RelativeStrengthAnalyzerV011().analyze(
        instrument_candles=_series([100, 110, 200]),
        market_candles=_series([100, 105, 110]),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
        horizon_bars=1,
    )
    assert result.instrument_return_pct == pytest.approx(10.0)
    assert result.market_return_pct == pytest.approx(5.0)


def test_insufficient_history_is_explicitly_unavailable():
    result = RelativeStrengthAnalyzerV011().analyze(
        instrument_candles=_series([100, 101]),
        market_candles=_series([100, 101]),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
        horizon_bars=2,
    )
    assert result.classification == "UNAVAILABLE"
    assert result.excess_return_pct is None
