from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


MARKET_BENCHMARK_RESOLVER_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class BenchmarkDefinition:
    """Canonical benchmark context resolved from instrument metadata only."""

    benchmark_id: str | None
    benchmark_kind: str
    market: str | None
    supported: bool
    reason: str
    version: str = MARKET_BENCHMARK_RESOLVER_VERSION


class MarketBenchmarkResolverV011:
    """Resolve a benchmark class without loading market prices or signals.

    The resolver is deliberately metadata-only. It must not perform network
    access, inspect candles, or silently fall back to an unrelated benchmark.
    """

    EQUITY_TYPES = frozenset({"STOCK", "EQUITY", "SHARE"})
    RUSSIAN_MARKETS = frozenset({"RU", "RUSSIA", "RUSSIAN", "MOEX", "MOEX_STOCK"})

    @staticmethod
    def _value(instrument: Any, *names: str) -> Any:
        for name in names:
            if isinstance(instrument, Mapping) and name in instrument:
                return instrument[name]
            if hasattr(instrument, name):
                return getattr(instrument, name)
        return None

    @classmethod
    def resolve(cls, instrument: Any) -> BenchmarkDefinition:
        instrument_type = cls._value(instrument, "instrument_type", "type", "kind")
        market = cls._value(instrument, "market", "market_id", "exchange", "exchange_id")

        normalized_type = str(instrument_type or "").strip().upper()
        normalized_market = str(market or "").strip().upper() or None

        if not normalized_type:
            return BenchmarkDefinition(
                benchmark_id=None,
                benchmark_kind="UNKNOWN",
                market=normalized_market,
                supported=False,
                reason="Instrument type is missing",
            )

        if normalized_type in cls.EQUITY_TYPES and normalized_market in cls.RUSSIAN_MARKETS:
            return BenchmarkDefinition(
                benchmark_id="IMOEX",
                benchmark_kind="EQUITY_MARKET",
                market=normalized_market,
                supported=True,
                reason="Russian equity instrument",
            )

        if normalized_type in cls.EQUITY_TYPES:
            return BenchmarkDefinition(
                benchmark_id=None,
                benchmark_kind="EQUITY_MARKET",
                market=normalized_market,
                supported=False,
                reason="Equity benchmark mapping is not configured for this market",
            )

        return BenchmarkDefinition(
            benchmark_id=None,
            benchmark_kind="UNSUPPORTED",
            market=normalized_market,
            supported=False,
            reason=f"Benchmark mapping is not configured for instrument type: {normalized_type}",
        )


__all__ = [
    "MARKET_BENCHMARK_RESOLVER_VERSION",
    "BenchmarkDefinition",
    "MarketBenchmarkResolverV011",
]
