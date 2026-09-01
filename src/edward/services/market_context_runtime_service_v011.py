from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from edward.services.benchmark_instrument_resolver_v011 import BenchmarkInstrumentResolverV011
from edward.services.market_benchmark_resolver_v011 import MarketBenchmarkResolverV011
from edward.services.market_context_snapshot_v011 import MarketContextSnapshotV011, resolve_context_status
from edward.services.market_data_loader_v011 import MarketDataLoaderV011, MarketDataRequest
from edward.services.market_regime_context_v011 import MarketRegimeContextBuilderV011
from edward.services.market_volatility_context_v011 import MarketVolatilityContextAnalyzerV011
from edward.services.relative_strength_analyzer_v011 import RelativeStrengthAnalyzerV011


MARKET_CONTEXT_RUNTIME_SERVICE_V011_VERSION = "0.11.0"
logger = logging.getLogger(__name__)


class MarketContextRuntimeServiceV011:
    """Runtime boundary that loads and builds point-in-time market context.

    Market context is additive evidence. If benchmark data is unavailable,
    the service returns an explicit UNAVAILABLE snapshot instead of failing
    the canonical instrument analysis.
    """

    def __init__(
        self,
        *,
        fetcher,
        indicatives_fetcher=None,
        find_instrument_fetcher=None,
        benchmark_resolver: type[MarketBenchmarkResolverV011] = MarketBenchmarkResolverV011,
        benchmark_instrument_resolver: BenchmarkInstrumentResolverV011 | None = None,
        context_builder: MarketRegimeContextBuilderV011 | None = None,
        relative_strength_analyzer: RelativeStrengthAnalyzerV011 | None = None,
        volatility_analyzer: MarketVolatilityContextAnalyzerV011 | None = None,
    ) -> None:
        self.loader = MarketDataLoaderV011(fetcher)
        self.benchmark_resolver = benchmark_resolver
        client = getattr(fetcher, "__self__", None)
        if indicatives_fetcher is None:
            indicatives_fetcher = getattr(client, "get_indicatives", None)
        if indicatives_fetcher is None:
            raise ValueError("Market context requires an Indicatives fetcher")
        if find_instrument_fetcher is None:
            find_instrument_fetcher = getattr(client, "find_instrument", None)
        self.benchmark_instrument_resolver = benchmark_instrument_resolver or BenchmarkInstrumentResolverV011(
            indicatives_fetcher,
            find_instrument_fetcher,
        )
        self.context_builder = context_builder or MarketRegimeContextBuilderV011()
        self.relative_strength_analyzer = relative_strength_analyzer or RelativeStrengthAnalyzerV011()
        self.volatility_analyzer = volatility_analyzer or MarketVolatilityContextAnalyzerV011()

    @staticmethod
    def _instrument_id(instrument_metadata: Mapping[str, Any] | Any) -> str:
        if isinstance(instrument_metadata, Mapping):
            return str(instrument_metadata.get("instrument_uid", instrument_metadata.get("uid", "")))
        return str(getattr(instrument_metadata, "instrument_uid", getattr(instrument_metadata, "uid", "")))

    @staticmethod
    def _unavailable_snapshot(*, instrument_id: str, as_of: datetime, benchmark_id: str) -> MarketContextSnapshotV011:
        return MarketContextSnapshotV011(
            instrument_id=instrument_id,
            as_of=as_of,
            benchmark_id=benchmark_id,
            benchmark_supported=True,
            market_regime=None,
            relative_strength=None,
            volatility=None,
            context_status="UNAVAILABLE",
        )

    @staticmethod
    def _log_unavailable(instrument_id: str, benchmark_id: str, exc: Exception) -> None:
        logger.warning(
            "[V011 MARKET CONTEXT] instrument=%s benchmark=%s status=UNAVAILABLE reason=BENCHMARK_DATA_UNAVAILABLE details=%s",
            instrument_id,
            benchmark_id,
            exc,
        )

    def build(
        self,
        *,
        instrument_metadata: Mapping[str, Any] | Any,
        asset_candles: Sequence[Any],
        as_of: datetime | None = None,
        limit: int = 2400,
        horizon_bars: int = 20,
    ) -> tuple[Any, MarketContextSnapshotV011]:
        if not asset_candles:
            raise ValueError("asset_candles are required")
        benchmark = self.benchmark_resolver.resolve(instrument_metadata)
        if not benchmark.supported or not benchmark.benchmark_id:
            raise ValueError(f"Market context is unsupported: {benchmark.reason}")

        effective_as_of = as_of or max(candle.timestamp for candle in asset_candles)
        instrument_id = self._instrument_id(instrument_metadata)

        try:
            resolved = self.benchmark_instrument_resolver.resolve(benchmark)
        except (ValueError, RuntimeError) as exc:
            self._log_unavailable(instrument_id, benchmark.benchmark_id, exc)
            return benchmark, self._unavailable_snapshot(
                instrument_id=instrument_id,
                as_of=effective_as_of,
                benchmark_id=benchmark.benchmark_id,
            )

        effective_start = min(candle.timestamp for candle in asset_candles)
        if effective_start >= effective_as_of:
            effective_start = effective_as_of - timedelta(days=1)

        try:
            market_candles = self.loader.load(
                MarketDataRequest(
                    instrument_id=resolved.instrument_uid,
                    start=effective_start,
                    end=effective_as_of,
                    limit=limit,
                )
            )
            if not market_candles:
                raise ValueError(f"No benchmark candles received for {resolved.instrument_uid}")
            market_regime = self.context_builder.build(
                instrument_id=resolved.instrument_uid,
                as_of=effective_as_of,
                candles=market_candles,
            )
            relative_strength = self.relative_strength_analyzer.analyze(
                instrument_candles=asset_candles,
                market_candles=market_candles,
                as_of=effective_as_of,
                horizon_bars=horizon_bars,
            )
            volatility = self.volatility_analyzer.analyze(
                instrument_candles=asset_candles,
                market_candles=market_candles,
                as_of=effective_as_of,
                horizon_bars=horizon_bars,
            )
            snapshot = MarketContextSnapshotV011(
                instrument_id=instrument_id,
                as_of=effective_as_of,
                benchmark_id=benchmark.benchmark_id,
                benchmark_supported=True,
                market_regime=market_regime,
                relative_strength=relative_strength,
                volatility=volatility,
                context_status=resolve_context_status(
                    benchmark_supported=True,
                    market_regime=market_regime,
                    relative_strength=relative_strength,
                    volatility=volatility,
                ),
            )
            if not snapshot.validate_point_in_time():
                raise ValueError("Market context failed point-in-time validation")
            return benchmark, snapshot
        except (ValueError, RuntimeError) as exc:
            self._log_unavailable(instrument_id, benchmark.benchmark_id, exc)
            return benchmark, self._unavailable_snapshot(
                instrument_id=instrument_id,
                as_of=effective_as_of,
                benchmark_id=benchmark.benchmark_id,
            )


__all__ = ["MARKET_CONTEXT_RUNTIME_SERVICE_V011_VERSION", "MarketContextRuntimeServiceV011"]
