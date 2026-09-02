from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.trading_path_adaptive_discovery_service_v014 import TradingPathAdaptiveDiscoveryServiceV014
from edward.services.trading_path_statistical_integrity_service_v014 import TradingPathStatisticalIntegrityServiceV014


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


def test_oos_changes_do_not_change_train_discovery():
    baseline_history = make_candles(120)
    changed_oos_history = list(baseline_history)

    for index in range(96, 120):
        timestamp = changed_oos_history[index].timestamp
        close = 250.0 - (index - 96) * 3.0
        changed_oos_history[index] = Candle(
            timestamp=timestamp,
            open=close + 0.5,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=5000.0 + index,
        )

    train_a, validation_a, oos_a = TradingPathStatisticalIntegrityServiceV014.partition_candles(baseline_history)
    train_b, validation_b, oos_b = TradingPathStatisticalIntegrityServiceV014.partition_candles(changed_oos_history)

    assert train_a == train_b
    assert validation_a == validation_b
    assert oos_a != oos_b

    discovery_a = TradingPathAdaptiveDiscoveryServiceV014.run(train_a)
    discovery_b = TradingPathAdaptiveDiscoveryServiceV014.run(train_b)
    assert discovery_a == discovery_b
