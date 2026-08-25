from __future__ import annotations

import sys
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import tinvest_candles_patch


class FakeState:
    def __init__(self):
        self.calls = []

    def _rest_request(self, method, payload):
        self.calls.append((method, payload))
        return {"candles": []}


def test_candles_request_uses_market_data_contract():
    state = FakeState()
    result = tinvest_candles_patch._candles(
        state,
        {
            "instrument_uid": "uid-1",
            "from": "2025-01-01T00:00:00Z",
            "to": "2026-01-01T00:00:00Z",
            "interval": "CANDLE_INTERVAL_DAY",
            "limit": 2400,
        },
    )

    assert result == {"candles": []}
    method, payload = state.calls[0]
    assert method == "MarketDataService/GetCandles"
    assert payload["instrumentId"] == "uid-1"
    assert payload["interval"] == "CANDLE_INTERVAL_DAY"
    assert payload["limit"] == 2400
    assert payload["candleSourceType"] == "CANDLE_SOURCE_EXCHANGE"
