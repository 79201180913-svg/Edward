from edward.services.strategy_confidence_policy_v06 import StrategyConfidencePolicy


def test_strategy_confidence_policy_is_used_for_failed_quality_gate():
    assert StrategyConfidencePolicy.resolve(quality_gate=False, confidence="High") == "N/A"


def test_strategy_confidence_policy_preserves_passed_strategy_confidence():
    assert StrategyConfidencePolicy.resolve(quality_gate=True, confidence="High") == "High"
