from edward.services.conditional_market_discovery_v011 import (
    ConditionalMarketDiscoveryV011,
    ConditionalObservationV011,
)


def test_discovery_calculates_conditional_statistics():
    observations = [
        ConditionalObservationV011(i, "TREND_UP", value)
        for i, value in enumerate([1.0, 2.0, -1.0, 3.0, 5.0])
    ]

    result = ConditionalMarketDiscoveryV011.discover(
        observations,
        condition="TREND_UP",
        min_observations=5,
    )

    assert result.observations == 5
    assert result.mean_future_return_pct == 2.0
    assert result.median_future_return_pct == 2.0
    assert result.positive_rate_pct == 80.0
    assert result.status == "SUFFICIENT"
    assert result.confidence_interval_95_pct is not None


def test_discovery_filters_by_condition():
    observations = [
        ConditionalObservationV011(1, "TREND_UP", 5.0),
        ConditionalObservationV011(2, "RANGE", -2.0),
        ConditionalObservationV011(3, "TREND_UP", 3.0),
    ]

    result = ConditionalMarketDiscoveryV011.discover(
        observations,
        condition="RANGE",
        min_observations=1,
    )

    assert result.observations == 1
    assert result.mean_future_return_pct == -2.0
    assert result.positive_rate_pct == 0.0
    assert result.status == "SUFFICIENT"


def test_discovery_marks_small_samples_as_research_only():
    observations = [ConditionalObservationV011(1, "HIGH_VOL", 4.0)]

    result = ConditionalMarketDiscoveryV011.discover(
        observations,
        condition="HIGH_VOL",
        min_observations=20,
    )

    assert result.observations == 1
    assert result.status == "INSUFFICIENT_SAMPLE"


def test_discovery_returns_unavailable_for_missing_condition():
    observations = [ConditionalObservationV011(1, "TREND_UP", 4.0)]

    result = ConditionalMarketDiscoveryV011.discover(
        observations,
        condition="RANGE",
    )

    assert result.observations == 0
    assert result.mean_future_return_pct is None
    assert result.status == "UNAVAILABLE"


def test_discover_many_preserves_requested_condition_order():
    observations = [
        ConditionalObservationV011(1, "A", 1.0),
        ConditionalObservationV011(2, "B", 2.0),
    ]

    results = ConditionalMarketDiscoveryV011.discover_many(
        observations,
        ["B", "A"],
        min_observations=1,
    )

    assert [item.condition for item in results] == ["B", "A"]
    assert [item.mean_future_return_pct for item in results] == [2.0, 1.0]
