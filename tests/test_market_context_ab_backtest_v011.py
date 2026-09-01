from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.market_context_ab_backtest_v011 import MarketContextABBacktestServiceV011, MarketContextABMetricV011
from edward.services.analysis_service import Candle


def _candles(count: int = 40):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(
        Candle(
            timestamp=start + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.0 + index,
            volume=1000.0,
        )
        for index in range(count)
    )


def _candidate(label: str = "IMPULSE_CONTINUATION", horizon: int = 3):
    rule = SimpleNamespace(
        hypothesis=label,
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=horizon,
    )
    return SimpleNamespace(candidate=SimpleNamespace(rule=rule))


def test_future_observations_strictly_exclude_cutoff_events():
    candles = _candles()
    service = MarketContextABBacktestServiceV011()
    observations = service.future_observations(candles, cutoff_index=20)

    assert observations
    assert min(item.index for item in observations) > 20


def test_aggregate_uses_trade_weighted_win_rate_and_window_statistics():
    service = MarketContextABBacktestServiceV011()
    metric = service.aggregate(((2.0, 100.0, 1), (-1.0, 0.0, 3)))

    assert isinstance(metric, MarketContextABMetricV011)
    assert metric.windows == 2
    assert metric.mean_oos_return_pct == 0.5
    assert metric.median_oos_return_pct == 0.5
    assert metric.total_trades == 4
    assert metric.win_rate_pct == 25.0
    assert metric.positive_windows == 1


def test_candidate_label_preserves_rule_identity():
    service = MarketContextABBacktestServiceV011()
    item = _candidate()

    assert service._candidate_label(item) == "IMPULSE_CONTINUATION/TREND_UP/Normal/Positive/H=3"
