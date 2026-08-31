from datetime import datetime, timezone

from edward.services.market_data_loader_v011 import MarketDataLoaderV011, MarketDataRequest


def test_loader_normalizes_tinvest_quotations_and_sorts_candles():
    calls = []

    def fetcher(instrument_id, start, end, interval, limit):
        calls.append((instrument_id, start, end, interval, limit))
        return {
            "candles": [
                {
                    "time": "2026-01-02T00:00:00+00:00",
                    "open": {"units": "102", "nano": 500000000},
                    "high": {"units": "105", "nano": 0},
                    "low": {"units": "101", "nano": 0},
                    "close": {"units": "104", "nano": 250000000},
                    "volume": 20,
                },
                {
                    "time": "2026-01-01T00:00:00+00:00",
                    "open": 100,
                    "high": 103,
                    "low": 99,
                    "close": 102,
                    "volume": 10,
                },
            ]
        }

    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 3, tzinfo=timezone.utc)
    candles = MarketDataLoaderV011(fetcher).load(
        MarketDataRequest("benchmark", start, end, limit=100)
    )

    assert len(candles) == 2
    assert candles[0].close == 102.0
    assert candles[1].close == 104.25
    assert candles[0].timestamp < candles[1].timestamp
    assert calls == [("benchmark", start, end, "CANDLE_INTERVAL_DAY", 100)]


def test_loader_rejects_invalid_window_and_limit():
    loader = MarketDataLoaderV011(lambda *args: {"candles": []})
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    try:
        loader.load(MarketDataRequest("x", now, now))
        assert False, "expected invalid window"
    except ValueError as exc:
        assert "earlier" in str(exc)

    try:
        loader.load(MarketDataRequest("x", datetime(2025, 1, 1, tzinfo=timezone.utc), now, limit=0))
        assert False, "expected invalid limit"
    except ValueError as exc:
        assert "positive" in str(exc)


def test_loader_does_not_extend_requested_end_time():
    captured = {}

    def fetcher(instrument_id, start, end, interval, limit):
        captured.update(start=start, end=end)
        return []

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    MarketDataLoaderV011(fetcher).load(MarketDataRequest("x", start, end))

    assert captured == {"start": start, "end": end}
