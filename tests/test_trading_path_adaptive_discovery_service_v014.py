from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.trading_path_adaptive_discovery_service_v014 import TradingPathAdaptiveDiscoveryServiceV014


def make_candles(count: int = 140) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []
    for index in range(count):
        close = 100.0 + index * 0.7
        candles.append(Candle(
            timestamp=start + timedelta(hours=index),
            open=close - 0.2,
            high=close + 0.8,
            low=close - 0.8,
            close=close,
            volume=1000.0 + index,
        ))
    return candles


def test_adaptive_discovery_is_deterministic():
    candles = make_candles()
    first = TradingPathAdaptiveDiscoveryServiceV014.run(candles)
    second = TradingPathAdaptiveDiscoveryServiceV014.run(candles)
    assert first == second
    assert first.version == "0.8.14"
    assert first.evaluated_rows > 0
    assert first.candidates


def test_discovery_emits_explicit_compact_rules():
    result = TradingPathAdaptiveDiscoveryServiceV014.run(make_candles())
    assert result.candidates
    for candidate in result.candidates:
        assert candidate.rule.regime != "UNKNOWN"
        assert 1 <= candidate.rule.complexity <= 3
        assert candidate.observations >= TradingPathAdaptiveDiscoveryServiceV014.MIN_OBSERVATIONS
        assert candidate.excess_return_pct > 0.0
        assert all(condition.operator in {">=", "<="} for condition in candidate.rule.conditions)
        assert all(not condition.feature.startswith("forward_") for condition in candidate.rule.conditions)


def test_discovery_uses_declared_percentile_grid():
    result = TradingPathAdaptiveDiscoveryServiceV014.run(make_candles())
    assert result.threshold_percentiles == (20, 40, 60, 80)
    assert all(candidate.rule.horizon in (1, 3, 5, 10, 20) for candidate in result.candidates)


def test_insufficient_history_returns_no_candidates():
    result = TradingPathAdaptiveDiscoveryServiceV014.run(make_candles(50))
    assert result.candidates == ()
    assert result.evaluated_rows == 0
