from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011


def _candles(count: int = 30, start_price: float = 100.0):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=start_price + i,
            high=start_price + i + 1,
            low=start_price + i - 1,
            close=start_price + i,
            volume=1000,
        )
        for i in range(count)
    ]


def test_runtime_builds_full_market_context_point_in_time():
    asset = _candles()
    market = _candles(start_price=200.0)
    calls = []

    def fetcher(instrument_id, start, end, interval, limit):
        calls.append((instrument_id, start, end, interval, limit))
        return {"candles": market}

    service = MarketContextRuntimeServiceV011(fetcher=fetcher)
    benchmark, snapshot = service.build(
        instrument_metadata={"uid": "asset-1", "instrument_type": "STOCK", "market": "MOEX"},
        asset_candles=asset,
    )

    assert benchmark.benchmark_id == "IMOEX"
    assert snapshot.instrument_id == "asset-1"
    assert snapshot.benchmark_id == "IMOEX"
    assert snapshot.context_status == "FULL"
    assert snapshot.market_regime is not None
    assert snapshot.relative_strength is not None
    assert snapshot.volatility is not None
    assert snapshot.validate_point_in_time() is True
    assert len(calls) == 1
    assert calls[0][0] == "IMOEX"
    assert calls[0][1] == asset[0].timestamp
    assert calls[0][2] == asset[-1].timestamp
    assert calls[0][3] == "CANDLE_INTERVAL_DAY"


def test_runtime_rejects_unsupported_instrument_before_fetch():
    calls = []

    def fetcher(*args):
        calls.append(args)
        return {"candles": []}

    service = MarketContextRuntimeServiceV011(fetcher=fetcher)
    with pytest.raises(ValueError, match="Market context is unsupported"):
        service.build(
            instrument_metadata={"uid": "bond-1", "instrument_type": "BOND", "market": "MOEX"},
            asset_candles=_candles(),
        )
    assert calls == []


def test_runtime_rejects_empty_benchmark_response():
    service = MarketContextRuntimeServiceV011(fetcher=lambda *args: {"candles": []})
    with pytest.raises(ValueError, match="No benchmark candles"):
        service.build(
            instrument_metadata={"uid": "asset-1", "instrument_type": "STOCK", "market": "MOEX"},
            asset_candles=_candles(),
        )
