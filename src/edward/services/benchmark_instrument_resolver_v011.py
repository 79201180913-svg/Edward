from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from edward.services.market_benchmark_resolver_v011 import BenchmarkDefinition


BENCHMARK_INSTRUMENT_RESOLVER_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class ResolvedBenchmarkInstrument:
    logical_benchmark_id: str
    instrument_uid: str
    ticker: str | None
    class_code: str | None
    source: str
    version: str = BENCHMARK_INSTRUMENT_RESOLVER_VERSION


class BenchmarkInstrumentResolverV011:
    """Resolve a logical benchmark to a real T-Invest instrument UID.

    The logical benchmark resolver and this broker-facing resolver are kept
    separate deliberately: ``IMOEX`` is a domain identifier, not a market-data
    instrument_id. Indicatives is the authoritative source for index/commodity
    instruments.
    """

    def __init__(self, indicatives_fetcher: Callable[[], Any]) -> None:
        self._indicatives_fetcher = indicatives_fetcher

    def resolve(self, benchmark: BenchmarkDefinition) -> ResolvedBenchmarkInstrument:
        logical_id = str(benchmark.benchmark_id or "").strip().upper()
        if not benchmark.supported or not logical_id:
            raise ValueError("Cannot resolve unsupported benchmark")

        response = self._indicatives_fetcher()
        items = self._items(response)
        exact = []
        for item in items:
            ticker = self._value(item, "ticker")
            uid = self._value(item, "uid", "instrument_uid", "instrumentUid")
            if str(ticker or "").strip().upper() == logical_id and uid:
                exact.append((item, str(uid)))

        if not exact:
            raise ValueError(f"Indicative benchmark not found: {logical_id}")
        if len(exact) > 1:
            raise ValueError(f"Indicative benchmark is ambiguous: {logical_id}")

        item, uid = exact[0]
        return ResolvedBenchmarkInstrument(
            logical_benchmark_id=logical_id,
            instrument_uid=uid,
            ticker=self._string(item, "ticker"),
            class_code=self._string(item, "class_code", "classCode"),
            source="INDICATIVES",
        )

    @staticmethod
    def _items(response: Any) -> list[Any]:
        if isinstance(response, list):
            return response
        if isinstance(response, Mapping):
            for key in ("indicatives", "instruments", "items"):
                value = response.get(key)
                if value is not None:
                    return list(value or [])
        for key in ("indicatives", "instruments", "items"):
            value = getattr(response, key, None)
            if value is not None:
                return list(value or [])
        return []

    @staticmethod
    def _value(item: Any, *names: str) -> Any:
        for name in names:
            if isinstance(item, Mapping) and name in item:
                return item[name]
            if hasattr(item, name):
                return getattr(item, name)
        return None

    @classmethod
    def _string(cls, item: Any, *names: str) -> str | None:
        value = cls._value(item, *names)
        text = str(value).strip() if value is not None else ""
        return text or None


__all__ = [
    "BENCHMARK_INSTRUMENT_RESOLVER_VERSION",
    "ResolvedBenchmarkInstrument",
    "BenchmarkInstrumentResolverV011",
]
