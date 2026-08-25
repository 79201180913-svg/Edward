from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.cached_analysis_service import CachedAnalysisService
from edward.services.strategy_optimization_cache import StrategyOptimizationCache
from edward.storage.sqlite_store import SQLiteStore


def _candles(count: int = 260) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(days=index),
            open=100.0 + index * 0.1,
            high=101.0 + index * 0.1,
            low=99.0 + index * 0.1,
            close=100.0 + index * 0.1,
            volume=1000.0,
        )
        for index in range(count)
    ]


def test_second_analysis_uses_cache_without_running_walk_forward(tmp_path, monkeypatch):
    store = SQLiteStore(tmp_path)
    candles = _candles()

    first = CachedAnalysisService(store)
    first.analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")
    assert first.last_cache_misses == 4
    assert first.last_cache_hits == 0

    second = CachedAnalysisService(store)

    def fail_walk_forward(*_args, **_kwargs):
        raise AssertionError("walk_forward must not run on a cache hit")

    monkeypatch.setattr(second, "walk_forward", fail_walk_forward)
    second_result = second.analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")

    assert len(second_result.strategies) == 4
    assert second.last_cache_hits == 4
    assert second.last_cache_misses == 0


def test_forced_recompute_ignores_cache(tmp_path):
    store = SQLiteStore(tmp_path)
    candles = _candles()

    CachedAnalysisService(store).analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")

    forced = CachedAnalysisService(store, force_recompute=True)
    forced.analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")

    assert forced.last_cache_hits == 0
    assert forced.last_cache_misses == 4


def test_changed_candles_invalidate_cache(tmp_path):
    store = SQLiteStore(tmp_path)
    candles = _candles()
    service = CachedAnalysisService(store)
    service.analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")

    changed = list(candles)
    changed[-1] = Candle(
        timestamp=changed[-1].timestamp,
        open=changed[-1].open,
        high=changed[-1].high,
        low=changed[-1].low,
        close=changed[-1].close + 1.0,
        volume=changed[-1].volume,
    )
    second = CachedAnalysisService(store)
    second.analyze(instrument_uid="uid-1", ticker="TEST", candles=changed, profile="speculative")

    assert second.last_cache_hits == 0
    assert second.last_cache_misses == 4


def test_clear_all_removes_walk_forward_cache(tmp_path):
    store = SQLiteStore(tmp_path)
    candles = _candles()
    CachedAnalysisService(store).analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")

    cache = StrategyOptimizationCache(tmp_path)
    assert cache.count() == 4
    assert cache.clear_all() == 4
    assert cache.count() == 0
