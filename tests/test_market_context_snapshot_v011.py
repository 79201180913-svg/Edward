from datetime import datetime, timedelta, timezone

from edward.services.market_context_snapshot_v011 import MarketContextSnapshotV011, resolve_context_status
from edward.services.market_regime_context_v011 import MarketRegimeContextV011


def _as_of():
    return datetime(2026, 1, 10, tzinfo=timezone.utc)


def test_full_context_status():
    assert resolve_context_status(
        benchmark_supported=True,
        market_regime=object(),
        relative_strength=object(),
        volatility=object(),
    ) == "FULL"


def test_partial_context_status_is_explicit():
    assert resolve_context_status(
        benchmark_supported=True,
        market_regime=object(),
        relative_strength=None,
        volatility=None,
    ) == "PARTIAL"


def test_unsupported_benchmark_is_unavailable():
    assert resolve_context_status(
        benchmark_supported=False,
        market_regime=object(),
        relative_strength=object(),
        volatility=object(),
    ) == "UNAVAILABLE"


def test_snapshot_rejects_future_nested_context():
    as_of = _as_of()
    future = MarketRegimeContextV011(
        instrument_id="IMOEX",
        as_of=as_of + timedelta(seconds=1),
        result=object(),
        source_candles=10,
    )
    snapshot = MarketContextSnapshotV011(
        instrument_id="TEST",
        as_of=as_of,
        benchmark_id="IMOEX",
        benchmark_supported=True,
        market_regime=future,
        relative_strength=None,
        volatility=None,
        context_status="PARTIAL",
    )
    assert snapshot.validate_point_in_time() is False


def test_snapshot_accepts_same_timestamp_context():
    as_of = _as_of()
    current = MarketRegimeContextV011(
        instrument_id="IMOEX",
        as_of=as_of,
        result=object(),
        source_candles=10,
    )
    snapshot = MarketContextSnapshotV011(
        instrument_id="TEST",
        as_of=as_of,
        benchmark_id="IMOEX",
        benchmark_supported=True,
        market_regime=current,
        relative_strength=None,
        volatility=None,
        context_status="PARTIAL",
    )
    assert snapshot.validate_point_in_time() is True
