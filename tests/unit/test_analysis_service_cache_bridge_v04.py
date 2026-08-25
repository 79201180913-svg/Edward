from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisService, Candle
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


def test_store_backed_analysis_service_uses_cache(tmp_path, monkeypatch):
    candles = _candles()
    store = SQLiteStore(tmp_path)

    first = AnalysisService(store)
    first.analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")

    second = AnalysisService(store)

    def fail_walk_forward(*_args, **_kwargs):
        raise AssertionError("walk_forward must not run after a valid cache hit")

    monkeypatch.setattr(second, "walk_forward", fail_walk_forward)
    result = second.analyze(instrument_uid="uid-1", ticker="TEST", candles=candles, profile="speculative")

    assert len(result.strategies) == 4
    assert second._last_cache_info["hits"] == 4
    assert second._last_cache_info["misses"] == 0
