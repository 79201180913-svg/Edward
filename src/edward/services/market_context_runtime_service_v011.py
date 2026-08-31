from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from edward.services.market_benchmark_resolver_v011 import MarketBenchmarkResolverV011
from edward.services.market_context_snapshot_v011 import MarketContextSnapshotV011
from edward.services.market_data_loader_v011 import MarketDataLoaderV011, MarketDataRequest
from edward.services.market_regime_context_v011 import MarketRegimeContextBuilderV011


MARKET_CONTEXT_RUNTIME_SERVICE_V011_VERSION = "0.11.0"


class MarketContextRuntimeServiceV011:
    """Runtime boundary that loads and builds point-in-time market context.

    The service is deliberately additive: it does not change strategy scores,
    Walk Forward, Quality Gate, or Trading Path decisions. It only supplies the
    market-context evidence that the v0.11 pipeline can expose to the runtime.
    """

    def __init__(
        self,
        *,
        fetcher,
        benchmark_resolver: type[MarketBenchmarkResolverV011] = MarketBenchmarkResolverV011,
        context_builder: MarketRegimeContextBuilderV011 | None = None,
    ) -> None:
        self.loader = MarketDataLoaderV011(fetcher)
        self.benchmark_resolver = benchmark_resolver
        self.context_builder = context_builder or MarketRegimeContextBuilderV011()

    def build(
        self,
        *,
        instrument_metadata: Mapping[str, Any] | Any,
        asset_candles: Sequence[Any],
        as_of: datetime | None = None,
        limit: int = 2400,
    ) -> tuple[Any, MarketContextSnapshotV011]:
        if not asset_candles:
            raise ValueError("asset_candles are required")
        benchmark = self.benchmark_resolver.resolve(instrument_metadata)
        if not benchmark.supported or not benchmark.benchmark_id:
            raise ValueError(f"Market context is unsupported: {benchmark.reason}")

        effective_as_of = as_of or max(candle.timestamp for candle in asset_candles)
        effective_start = min(candle.timestamp for candle in asset_candles)
        if effective_start >= effective_as_of:
            effective_start = effective_as_of - timedelta(days=1)

        market_candles = self.loader.load(
            MarketDataRequest(
                instrument_id=benchmark.benchmark_id,
                start=effective_start,
                end=effective_as_of,
                limit=limit,
            )
        )
        if not market_candles:
            raise ValueError(f"No benchmark candles received for {benchmark.benchmark_id}")

        context = self.context_builder.build(
            instrument_id=benchmark.benchmark_id,
            as_of=effective_as_of,
            candles=market_candles,
        )
        return benchmark, context


__all__ = [
    "MARKET_CONTEXT_RUNTIME_SERVICE_V011_VERSION",
    "MarketContextRuntimeServiceV011",
]
