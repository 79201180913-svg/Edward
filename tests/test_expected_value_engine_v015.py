from edward.services.expected_value_engine_v08 import ExpectedValueEngine
from edward.services.trading_path_ev_evidence_service_v015 import TradingPathEVEvidenceServiceV015


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


def test_v015_ev_evidence_separates_positive_ev_from_statistical_confirmation():
    evidence = TradingPathEVEvidenceServiceV015.build((1.0, -1.0, 1.0, -0.5))
    assert evidence.positive_ev is True
    assert evidence.statistically_positive_ev is False
    assert evidence.status == "READY"


def test_v015_ev_evidence_marks_ci_supported_edge():
    evidence = TradingPathEVEvidenceServiceV015.build((1.0,) * 40)
    assert evidence.positive_ev is True
    assert evidence.statistically_positive_ev is True
    assert evidence.status == "READY"
    assert evidence.confidence_score >= 75.0


def test_v015_ev_evidence_does_not_turn_negative_ev_into_positive_edge():
    evidence = TradingPathEVEvidenceServiceV015.build((-1.0,) * 40)
    assert evidence.positive_ev is False
    assert evidence.statistically_positive_ev is False
    assert evidence.status == "READY"
