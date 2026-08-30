from edward.services.failure_attribution_v084 import FailureAttributionServiceV084


def test_no_viable_train_is_primary_reason() -> None:
    result = FailureAttributionServiceV084.evaluate(strategy="Breakout", quality_gate_passed=False, quality_gate_failure_reason="return_consistency", viable_windows=0)
    assert result.primary_reason == "NO_VIABLE_TRAIN"


def test_negative_oos_is_primary_over_secondary_diagnostics() -> None:
    result = FailureAttributionServiceV084.evaluate(strategy="Breakout", quality_gate_passed=False, quality_gate_failure_reason="sharpe_consistency", low_sample_pct=80.0, oos_mean_return_pct=-2.0, oos_positive_pct=25.0, stable_zone_pct=20.0, viable_windows=4)
    assert result.primary_reason == "OOS_NEGATIVE"
    assert "LOW_SAMPLE" in result.supporting_reasons
    assert "LOW_PARAMETER_STABILITY" in result.supporting_reasons


def test_passed_strategy_has_pass_attribution() -> None:
    result = FailureAttributionServiceV084.evaluate(strategy="Momentum", quality_gate_passed=True, quality_gate_failure_reason=None, viable_windows=4)
    assert result.primary_reason == "PASS"
    assert result.supporting_reasons == ()
