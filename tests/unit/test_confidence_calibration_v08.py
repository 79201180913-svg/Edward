from edward.services.confidence_calibration_v08 import calculate_confidence


def test_small_sample_is_low_confidence_even_with_good_components():
    result = calculate_confidence(
        strategy_quality=80,
        forecast_quality=80,
        regime_confidence=80,
        portfolio_confidence=80,
        observations=47,
        uncertainty_width_pct=10,
    )

    assert result.level == "Low"
    assert result.overall_confidence < 60


def test_large_sample_can_reach_high_confidence_when_evidence_is_strong():
    result = calculate_confidence(
        strategy_quality=90,
        forecast_quality=90,
        regime_confidence=80,
        portfolio_confidence=85,
        observations=150,
        uncertainty_width_pct=5,
    )

    assert result.level == "High"
    assert result.overall_confidence >= 75
