from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.trading_path_market_context_service_v015 import (
    TradingPathMarketContextServiceV015,
)


def test_market_context_calculates_instrument_regime_and_market_excess():
    result = TradingPathMarketContextServiceV015.build(
        instrument_return_pct=8.0,
        instrument_baseline_return_pct=3.0,
        regime_baseline_return_pct=2.0,
        market_return_pct=5.0,
        benchmark_id="IMOEX",
    )

    assert result.instrument_excess_pct == 5.0
    assert result.regime_excess_pct == 6.0
    assert result.market_excess_pct == 3.0
    assert result.relative_strength_pct == 3.0
    assert result.context_status == "FULL"
    assert result.benchmark_id == "IMOEX"


def test_market_context_is_partial_without_regime_baseline():
    result = TradingPathMarketContextServiceV015.build(
        instrument_return_pct=8.0,
        instrument_baseline_return_pct=3.0,
        regime_baseline_return_pct=None,
        market_return_pct=5.0,
    )

    assert result.instrument_excess_pct == 5.0
    assert result.regime_excess_pct is None
    assert result.market_excess_pct == 3.0
    assert result.relative_strength_pct == 3.0
    assert result.context_status == "PARTIAL"


def test_market_context_is_unavailable_without_relative_benchmarks():
    result = TradingPathMarketContextServiceV015.build(
        instrument_return_pct=8.0,
        instrument_baseline_return_pct=3.0,
        regime_baseline_return_pct=None,
        market_return_pct=None,
    )

    assert result.instrument_excess_pct == 5.0
    assert result.regime_excess_pct is None
    assert result.market_excess_pct is None
    assert result.relative_strength_pct is None
    assert result.context_status == "UNAVAILABLE"


def test_market_context_preserves_missing_instrument_return():
    result = TradingPathMarketContextServiceV015.build(
        instrument_return_pct=None,
        instrument_baseline_return_pct=3.0,
        regime_baseline_return_pct=2.0,
        market_return_pct=5.0,
        benchmark_id="IMOEX",
    )

    assert result.instrument_return_pct is None
    assert result.instrument_excess_pct is None
    assert result.regime_excess_pct is None
    assert result.market_excess_pct is None
    assert result.relative_strength_pct is None
    assert result.context_status == "UNAVAILABLE"


def test_market_context_rounds_floating_point_noise():
    result = TradingPathMarketContextServiceV015.build(
        instrument_return_pct=0.47500000000000003,
        instrument_baseline_return_pct=0.125,
        regime_baseline_return_pct=0.2,
        market_return_pct=0.3,
    )

    assert result.instrument_return_pct == 0.475
    assert result.instrument_excess_pct == 0.35
    assert result.regime_excess_pct == 0.275
    assert result.market_excess_pct == 0.175


def _candles(values: list[float]) -> tuple[Candle, ...]:
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(
        Candle(
            timestamp=origin + timedelta(hours=index),
            open=value,
            high=value,
            low=value,
            close=value,
        )
        for index, value in enumerate(values)
    )


def _trend_up_values(count: int) -> list[float]:
    """Create deterministic history that MarketRegimeEngineV08 classifies as TREND_UP."""
    values = [100.0]
    for index in range(count - 1):
        step = 0.005 if index % 2 == 0 else 0.025
        values.append(values[-1] * (1.0 + step))
    return values


def test_market_context_from_oos_uses_same_time_range_and_point_in_time_regime_baseline():
    instrument = _candles(_trend_up_values(120))
    benchmark = _candles([100.0 + index * 0.5 for index in range(120)])
    candidate = SimpleNamespace(rule=SimpleNamespace(regime="TREND_UP", horizon=5))
    windows = (SimpleNamespace(start=90, end=120, mean_return_pct=4.0, baseline_return_pct=1.0),)

    result = TradingPathMarketContextServiceV015.build_from_oos(
        candidate=candidate,
        instrument_candles=instrument,
        benchmark_candles=benchmark,
        oos_windows=windows,
        benchmark_id="IMOEX",
    )

    assert result.instrument_return_pct == 4.0
    assert result.instrument_baseline_return_pct == 1.0
    assert result.market_return_pct is not None
    assert result.regime_baseline_return_pct is not None
    assert result.market_excess_pct is not None
    assert result.regime_excess_pct is not None
    assert result.context_status == "FULL"
    assert result.relative_strength_pct == result.market_excess_pct


def test_market_context_from_oos_is_partial_without_benchmark():
    instrument = _candles([100.0 + index * 0.2 for index in range(120)])
    candidate = SimpleNamespace(rule=SimpleNamespace(regime="TREND_UP", horizon=5))
    windows = (SimpleNamespace(start=90, end=120, mean_return_pct=4.0, baseline_return_pct=1.0),)

    result = TradingPathMarketContextServiceV015.build_from_oos(
        candidate=candidate,
        instrument_candles=instrument,
        benchmark_candles=None,
        oos_windows=windows,
    )

    assert result.instrument_excess_pct == 3.0
    assert result.market_return_pct is None
    assert result.regime_baseline_return_pct is None
    assert result.context_status == "UNAVAILABLE"
