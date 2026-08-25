from edward.services.forecast_trade_cache_service import (
    ForecastTradeCacheKey,
    ForecastTradeCacheService,
)


def key(**overrides):
    data = dict(
        instrument_uid="uid-1",
        profile="medium_term",
        risk_profile="balanced",
        forecast_model="HistoricalDrift",
        horizon=5,
        data_snapshot="snapshot-1",
        algorithm_version="0.5.0",
    )
    data.update(overrides)
    return ForecastTradeCacheKey(**data)


def test_cache_miss_then_hit():
    cache = ForecastTradeCacheService()
    assert cache.get(key()) is None
    cache.put(key(), {"forecast": 123})
    assert cache.get(key()) == {"forecast": 123}
    assert cache.stats().misses == 1
    assert cache.stats().hits == 1


def test_snapshot_change_creates_different_entry():
    cache = ForecastTradeCacheService()
    cache.put(key(), "old")
    cache.put(key(data_snapshot="snapshot-2"), "new")
    assert cache.get(key()) == "old"
    assert cache.get(key(data_snapshot="snapshot-2")) == "new"
    assert cache.stats().entries == 2


def test_algorithm_version_change_creates_different_entry():
    cache = ForecastTradeCacheService()
    cache.put(key(), "v1")
    cache.put(key(algorithm_version="0.5.1"), "v2")
    assert cache.get(key()) == "v1"
    assert cache.get(key(algorithm_version="0.5.1")) == "v2"


def test_profile_and_risk_profile_do_not_leak():
    cache = ForecastTradeCacheService()
    cache.put(key(profile="medium_term", risk_profile="balanced"), "medium")
    cache.put(key(profile="long_term", risk_profile="conservative"), "long")
    assert cache.get(key(profile="medium_term", risk_profile="balanced")) == "medium"
    assert cache.get(key(profile="long_term", risk_profile="conservative")) == "long"
    assert cache.get(key(profile="long_term", risk_profile="balanced")) is None


def test_invalidate_instrument_removes_only_that_instrument():
    cache = ForecastTradeCacheService()
    cache.put(key(instrument_uid="uid-1"), "one")
    cache.put(key(instrument_uid="uid-2"), "two")
    assert cache.invalidate(instrument_uid="uid-1") == 1
    assert cache.get(key(instrument_uid="uid-1")) is None
    assert cache.get(key(instrument_uid="uid-2")) == "two"


def test_clear_removes_all_entries_and_snapshot_is_clean():
    cache = ForecastTradeCacheService()
    cache.put(key(), "one")
    cache.put(key(horizon=20), "two")
    cache.clear()
    assert cache.stats().entries == 0
    assert cache.snapshot()["entries"] == 0


def test_key_is_deterministic():
    assert key().as_string() == key().as_string()
    assert key().as_string() != key(horizon=20).as_string()
