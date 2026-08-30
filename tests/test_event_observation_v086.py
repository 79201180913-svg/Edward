from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import EventObservationBuilderV086


def _candles(count: int = 180) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    result = []
    for i in range(count):
        previous = price
        if i % 37 == 0 and i > 25:
            price *= 1.035
        elif i % 43 == 0 and i > 25:
            price *= 0.965
        else:
            price *= 1.0015 if (i // 12) % 2 == 0 else 0.999
        result.append(Candle(start + timedelta(hours=i), previous, max(previous, price) * 1.002, min(previous, price) * 0.998, price, 1000.0))
    return result


def test_event_observations_are_canonical_and_have_all_horizons():
    observations = EventObservationBuilderV086.build(_candles())
    assert observations
    assert all(observation.hypothesis for observation in observations)
    assert all(observation.regime for observation in observations)
    assert all(observation.volatility_bucket in {"Low", "Normal", "High"} for observation in observations)
    assert all(observation.direction in {"Positive", "Negative"} for observation in observations)
    assert all(len(observation.forward_returns_pct) == 5 for observation in observations)


def test_event_observation_forward_return_accessor_is_consistent():
    observations = EventObservationBuilderV086.build(_candles())
    for observation in observations:
        assert observation.forward_return(1) == dict(observation.forward_returns_pct)[1]
        assert observation.forward_return(999) is None


def test_event_observations_are_sorted_by_hypothesis_then_index():
    observations = EventObservationBuilderV086.build(_candles())
    keys = [(item.hypothesis, item.index) for item in observations]
    assert keys == sorted(keys)
