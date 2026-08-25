from __future__ import annotations

from edward.api.candles_client_patch import install


class FakeClient:
    def __init__(self):
        self.calls = []

    def _request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        return {"candles": []}


def test_client_patch_adds_get_candles():
    install(FakeClient)
    client = FakeClient()
    result = client.get_candles("uid-1", days=100)

    assert result == {"candles": []}
    method, path, payload = client.calls[0]
    assert method == "POST"
    assert path == "/market/candles"
    assert payload["instrument_id"] == "uid-1"
    assert payload["interval"] == "CANDLE_INTERVAL_DAY"
    assert payload["limit"] == 2400
