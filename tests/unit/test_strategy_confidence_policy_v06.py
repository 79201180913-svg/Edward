from edward.services.strategy_confidence_policy_v06 import StrategyConfidencePolicy


def test_failed_quality_gate_forces_strategy_confidence_to_na():
    for confidence in ("Low", "Medium", "High", None):
        assert StrategyConfidencePolicy.resolve(quality_gate=False, confidence=confidence) == "N/A"


def test_passed_quality_gate_preserves_valid_strategy_confidence():
    for confidence in ("Low", "Medium", "High"):
        assert StrategyConfidencePolicy.resolve(quality_gate=True, confidence=confidence) == confidence


def test_passed_quality_gate_defaults_invalid_confidence_to_low():
    assert StrategyConfidencePolicy.resolve(quality_gate=True, confidence=None) == "Low"
    assert StrategyConfidencePolicy.resolve(quality_gate=True, confidence="unknown") == "Low"


def test_policy_validation_rejects_invalid_combinations():
    StrategyConfidencePolicy.validate(quality_gate=False, confidence="High")
    StrategyConfidencePolicy.validate(quality_gate=True, confidence="High")
