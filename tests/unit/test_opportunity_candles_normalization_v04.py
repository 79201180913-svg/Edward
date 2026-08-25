from types import SimpleNamespace
from datetime import datetime, timezone

from edward.services.opportunity_search_service import OpportunitySearchService


def test_get_candles_accepts_object_response_and_timestamp_objects():
    service = OpportunitySearchService.__new__(OpportunitySearchService)

    candle = SimpleNamespace(
        time=SimpleNamespace(seconds=1735689600, nanos=0),
        open=SimpleNamespace(units=10, nano=0),
        high=SimpleNamespace(units=11, nano=0),
        low=SimpleNamespace(units=9, nano=0),
        close=SimpleNamespace(units=10, nano=0),
        volume=100,
    )
    payload = SimpleNamespace(candles=[candle] * 150)

    class FakeClient:
        def get_candles(self, *_args, **_kwargs):
            return payload

    service.client = FakeClient()
    candles = service._get_candles("uid")

    assert len(candles) == 150
    assert candles[0].close == 10.0
    assert candles[0].timestamp == datetime(2025, 1, 1, tzinfo=timezone.utc)
