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
