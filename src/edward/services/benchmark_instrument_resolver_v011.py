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

    Indicatives is the authoritative source for index/commodity instruments.
    A FindInstrument fallback is supported for environments where the
    Indicatives endpoint is unavailable (notably some sandbox adapter/runtime
    combinations). The fallback is explicitly restricted to INDEX instruments
    and non-tradable search results, so a normal share with the same ticker
    cannot silently become the benchmark.
    """

    def __init__(
        self,
        indicatives_fetcher: Callable[[], Any],
        find_instrument_fetcher: Callable[[str, bool], Any] | None = None,
    ) -> None:
        self._indicatives_fetcher = indicatives_fetcher
        self._find_instrument_fetcher = find_instrument_fetcher

    def resolve(self, benchmark: BenchmarkDefinition) -> ResolvedBenchmarkInstrument:
        logical_id = str(benchmark.benchmark_id or "").strip().upper()
        if not benchmark.supported or not logical_id:
            raise ValueError("Cannot resolve unsupported benchmark")

        try:
            response = self._indicatives_fetcher()
            exact = self._match(self._items(response), logical_id)
            if not exact:
                raise ValueError(f"Indicative benchmark not found: {logical_id}")
            return self._resolved(exact, logical_id, "INDICATIVES")
        except Exception as exc:
            if not self._is_not_found(exc) or self._find_instrument_fetcher is None:
                raise

        response = self._find_instrument_fetcher(logical_id, False)
        exact = self._match_index_search(self._items(response), logical_id)
        if not exact:
            raise ValueError(f"Index benchmark not found by FindInstrument fallback: {logical_id}")
        return self._resolved(exact, logical_id, "FIND_INSTRUMENT_FALLBACK")

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        error_code = str(getattr(exc, "error_code", "") or "").strip().lower()
        return status_code == 404 or error_code in {"not_found", "404"}

    @classmethod
    def _match(cls, items: list[Any], logical_id: str) -> list[tuple[Any, str]]:
        exact: list[tuple[Any, str]] = []
        for item in items:
            ticker = cls._value(item, "ticker")
            uid = cls._value(item, "uid", "instrument_uid", "instrumentUid")
            if str(ticker or "").strip().upper() == logical_id and uid:
                exact.append((item, str(uid)))
        return exact

    @classmethod
    def _match_index_search(cls, items: list[Any], logical_id: str) -> list[tuple[Any, str]]:
        exact: list[tuple[Any, str]] = []
        for item in items:
            ticker = cls._value(item, "ticker")
            uid = cls._value(item, "uid", "instrument_uid", "instrumentUid")
            kind = str(cls._value(item, "instrument_kind", "instrumentKind", "instrument_type", "instrumentType") or "").upper()
            if str(ticker or "").strip().upper() != logical_id or not uid:
                continue
            if kind in {"INDEX", "INSTRUMENT_TYPE_INDEX", "9"}:
                exact.append((item, str(uid)))
        return exact

    @classmethod
    def _resolved(cls, exact: list[tuple[Any, str]], logical_id: str, source: str) -> ResolvedBenchmarkInstrument:
        if len(exact) > 1:
            raise ValueError(f"Indicative benchmark is ambiguous: {logical_id}")
        item, uid = exact[0]
        return ResolvedBenchmarkInstrument(
            logical_benchmark_id=logical_id,
            instrument_uid=uid,
            ticker=cls._string(item, "ticker"),
            class_code=cls._string(item, "class_code", "classCode"),
            source=source,
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
