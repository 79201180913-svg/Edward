from datetime import datetime, timezone

from edward.api.candles_client_patch import install


class FakeClient:
    def __init__(self):
        self.calls = []

    def _request(self, method, path, payload):
        self.calls.append((method, path, payload))
        return {"candles": []}


def test_candles_patch_preserves_five_argument_runtime_boundary():
    install(FakeClient)
    client = FakeClient()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, tzinfo=timezone.utc)

    client.get_candles("IMOEX", start, end, "CANDLE_INTERVAL_DAY", 2400)

    assert len(client.calls) == 1
    method, path, payload = client.calls[0]
    assert method == "POST"
    assert path == "/market/candles"
    assert payload == {
        "instrument_id": "IMOEX",
        "from": "2026-01-01T00:00:00Z",
        "to": "2026-08-31T00:00:00Z",
        "interval": "CANDLE_INTERVAL_DAY",
        "limit": 2400,
    }


def test_candles_patch_keeps_legacy_days_call_compatible():
    install(FakeClient)
    client = FakeClient()

    client.get_candles("IMOEX", interval="CANDLE_INTERVAL_DAY", days=2400)

    assert len(client.calls) == 1
    payload = client.calls[0][2]
    assert payload["instrument_id"] == "IMOEX"
    assert payload["interval"] == "CANDLE_INTERVAL_DAY"
    assert payload["limit"] == 2400
    assert payload["from"].endswith("Z")
    assert payload["to"].endswith("Z")
