from edward.services.expected_value_engine_v08 import ExpectedValueEngine


def test_positive_ev_with_wide_ci_has_low_reliability():
    result = ExpectedValueEngine.from_returns((1.0, -1.0, 1.0, -0.5))
    assert result.expected_value_pct > 0
    assert result.ev_ci_low_pct is not None
    assert result.ev_ci_low_pct < 0
    assert result.edge_reliability_level == "LOW"


def test_positive_ev_with_ci_above_zero_has_reliable_edge():
    result = ExpectedValueEngine.from_returns((1.0,) * 40)
    assert result.expected_value_pct == 1.0
    assert result.ev_ci_low_pct == 1.0
    assert result.ev_ci_high_pct == 1.0
    assert result.edge_reliability_pct == 100.0
    assert result.edge_reliability_level == "MEDIUM"


def test_negative_ev_never_gets_positive_edge_reliability():
    result = ExpectedValueEngine.from_returns((-1.0,) * 40)
    assert result.expected_value_pct == -1.0
    assert result.ev_ci_high_pct == -1.0
    assert result.edge_reliability_pct == 0.0
    assert result.edge_reliability_level == "LOW"


def test_confidence_is_still_observation_based_but_edge_reliability_is_separate():
    result = ExpectedValueEngine.from_returns((0.1,) * 100)
    assert result.confidence == "High"
    assert result.edge_reliability_level == "HIGH"
    assert result.edge_reliability_pct == 100.0
