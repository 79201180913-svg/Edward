from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011


def _candles(count: int = 30, start_price: float = 100.0):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(timestamp=start + timedelta(days=i), open=start_price + i, high=start_price + i + 1, low=start_price + i - 1, close=start_price + i, volume=1000)
        for i in range(count)
    ]


def test_runtime_resolves_logical_benchmark_to_uid_before_fetch():
    asset = _candles()
    market = _candles(start_price=200.0)
    candle_calls = []
    indicative_calls = []

    def fetcher(instrument_id, start, end, interval, limit):
        candle_calls.append((instrument_id, start, end, interval, limit))
        return {"candles": market}

    def indicatives_fetcher():
        indicative_calls.append(True)
        return {"indicatives": [{"uid": "imoex-uid", "ticker": "IMOEX", "class_code": "INDX", "name": "MOEX Russia Index"}]}

    service = MarketContextRuntimeServiceV011(fetcher=fetcher, indicatives_fetcher=indicatives_fetcher)
    benchmark, snapshot = service.build(
        instrument_metadata={"uid": "asset-1", "instrument_type": "STOCK", "class_code": "TQBR"},
        asset_candles=asset,
    )

    assert benchmark.benchmark_id == "IMOEX"
    assert snapshot.instrument_id == "asset-1"
    assert snapshot.benchmark_id == "IMOEX"
    assert snapshot.context_status == "FULL"
    assert snapshot.validate_point_in_time() is True
    assert indicative_calls == [True]
    assert len(candle_calls) == 1
    assert candle_calls[0][0] == "imoex-uid"
    assert candle_calls[0][1] == asset[0].timestamp
    assert candle_calls[0][2] == asset[-1].timestamp
    assert candle_calls[0][3] == "CANDLE_INTERVAL_DAY"


def test_runtime_rejects_unsupported_instrument_before_fetch():
    calls = []

    def fetcher(*args):
        calls.append(args)
        return {"candles": []}

    service = MarketContextRuntimeServiceV011(fetcher=fetcher, indicatives_fetcher=lambda: {"indicatives": []})
    benchmark, snapshot = service.build(
        instrument_metadata={"uid": "bond-1", "instrument_type": "BOND", "market": "MOEX"},
        asset_candles=_candles(),
    )
    assert benchmark.supported is False
    assert snapshot.context_status == "UNAVAILABLE"
    assert snapshot.context_reason is not None
    assert calls == []


def test_runtime_returns_unavailable_when_benchmark_cannot_be_resolved():
    service = MarketContextRuntimeServiceV011(
        fetcher=lambda *args: {"candles": _candles()},
        indicatives_fetcher=lambda: {"indicatives": []},
        find_instrument_fetcher=lambda *args: {"instruments": []},
    )
    benchmark, snapshot = service.build(
        instrument_metadata={"uid": "asset-1", "instrument_type": "STOCK", "market": "MOEX"},
        asset_candles=_candles(),
    )
    assert benchmark.benchmark_id == "IMOEX"
    assert snapshot.context_status == "UNAVAILABLE"
    assert snapshot.context_reason is not None


def test_runtime_returns_unavailable_when_market_candles_fail():
    def fetcher(*args):
        raise RuntimeError("benchmark candles unavailable")

    service = MarketContextRuntimeServiceV011(
        fetcher=fetcher,
        indicatives_fetcher=lambda: {"indicatives": [{"uid": "imoex-uid", "ticker": "IMOEX"}]},
    )
    benchmark, snapshot = service.build(
        instrument_metadata={"uid": "asset-1", "instrument_type": "STOCK", "market": "MOEX"},
        asset_candles=_candles(),
    )
    assert benchmark.benchmark_id == "IMOEX"
    assert snapshot.context_status == "UNAVAILABLE"
    assert "BENCHMARK_DATA_UNAVAILABLE" in (snapshot.context_reason or "")
