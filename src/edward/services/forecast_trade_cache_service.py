from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


CACHE_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class ForecastTradeCacheKey:
    instrument_uid: str
    profile: str
    risk_profile: str
    forecast_model: str
    horizon: int
    data_snapshot: str
    algorithm_version: str

    def as_string(self) -> str:
        payload = {
            "instrument_uid": self.instrument_uid,
            "profile": self.profile,
            "risk_profile": self.risk_profile,
            "forecast_model": self.forecast_model,
            "horizon": self.horizon,
            "data_snapshot": self.data_snapshot,
            "algorithm_version": self.algorithm_version,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CacheStats:
    entries: int
    hits: int
    misses: int


class ForecastTradeCacheService:
    """In-memory versioned cache for forecast and trade-plan results."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._keys: dict[str, ForecastTradeCacheKey] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: ForecastTradeCacheKey) -> Any | None:
        cache_key = key.as_string()
        if cache_key in self._store:
            self._hits += 1
            return self._store[cache_key]
        self._misses += 1
        return None

    def put(self, key: ForecastTradeCacheKey, value: Any) -> None:
        cache_key = key.as_string()
        self._store[cache_key] = value
        self._keys[cache_key] = key

    def invalidate(self, *, instrument_uid: str | None = None) -> int:
        if instrument_uid is None:
            count = len(self._store)
            self.clear()
            return count

        to_delete = [
            cache_key
            for cache_key, key in self._keys.items()
            if key.instrument_uid == str(instrument_uid)
        ]
        for cache_key in to_delete:
            self._store.pop(cache_key, None)
            self._keys.pop(cache_key, None)
        return len(to_delete)

    def clear(self) -> None:
        self._store.clear()
        self._keys.clear()

    def stats(self) -> CacheStats:
        return CacheStats(
            entries=len(self._store),
            hits=self._hits,
            misses=self._misses,
        )

    def snapshot(self) -> dict[str, int]:
        stats = self.stats()
        return {"entries": stats.entries, "hits": stats.hits, "misses": stats.misses}
