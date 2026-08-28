from edward.services.expected_value_engine_v08 import ExpectedValueEngine


def test_small_sample_reports_wide_ev_interval_and_low_reliability():
    result = ExpectedValueEngine.from_returns([10.0, -2.0, 8.0, -3.0, 7.0, -4.0, 6.0, -5.0])

    assert result.available is True
    assert result.observations == 8
    assert result.expected_value_pct > 0
    assert result.ev_ci_low_pct is not None
    assert result.ev_ci_high_pct is not None
    assert result.ev_ci_low_pct < 0 < result.ev_ci_high_pct
    assert result.edge_reliability_pct is not None
    assert result.edge_reliability_level == "LOW"


def test_large_stable_sample_can_confirm_positive_expected_value():
    result = ExpectedValueEngine.from_returns([2.0] * 120)

    assert result.available is True
    assert result.observations == 120
    assert result.expected_value_pct == 2.0
    assert result.ev_ci_low_pct == 2.0
    assert result.ev_ci_high_pct == 2.0
    assert result.edge_reliability_pct == 100.0
    assert result.edge_reliability_level == "HIGH"
