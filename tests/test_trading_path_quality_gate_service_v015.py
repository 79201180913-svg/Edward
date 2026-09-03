from types import SimpleNamespace

from edward.services.trading_path_quality_gate_service_v015 import TradingPathQualityGateServiceV015


def _inputs(**overrides):
    values = dict(
        validation=SimpleNamespace(statistical_valid=True, overlap_valid=True, multiple_testing_valid=True),
        wf_summary=SimpleNamespace(passed=True),
        independent_oos_evidence=SimpleNamespace(
            status="READY", parameters_locked=True, excess_return_pct=2.0, worst_window_excess_pct=1.0,
        ),
        market_context=SimpleNamespace(context_status="FULL", regime_excess_pct=1.5, market_excess_pct=1.0),
        risk_gate=True,
        current_state="entry_ready",
    )
    values.update(overrides)
    return values


def test_quality_gate_requires_all_critical_gates():
    result = TradingPathQualityGateServiceV015.evaluate(**_inputs())

    assert result.passed is True
    assert result.statistical_gate is True
    assert result.wf_gate is True
    assert result.oos_gate is True
    assert result.market_context_gate is True
    assert result.risk_gate is True
    assert result.current_state_gate is True
    assert result.reasons == ()


def test_quality_gate_does_not_allow_oos_failure_to_be_compensated():
    result = TradingPathQualityGateServiceV015.evaluate(
        **_inputs(independent_oos_evidence=SimpleNamespace(
            status="READY", parameters_locked=True, excess_return_pct=-1.0, worst_window_excess_pct=-2.0,
        ))
    )

    assert result.passed is False
    assert result.oos_gate is False
    assert "OOS_GATE_FAILED" in result.reasons


def test_quality_gate_rejects_missing_market_context():
    result = TradingPathQualityGateServiceV015.evaluate(
        **_inputs(market_context=SimpleNamespace(
            context_status="PARTIAL", regime_excess_pct=1.5, market_excess_pct=None,
        ))
    )

    assert result.passed is False
    assert result.market_context_gate is False
    assert "MARKET_CONTEXT_GATE_FAILED" in result.reasons


def test_quality_gate_rejects_statistical_failure_even_when_other_gates_pass():
    result = TradingPathQualityGateServiceV015.evaluate(
        **_inputs(validation=SimpleNamespace(
            statistical_valid=False, overlap_valid=True, multiple_testing_valid=True,
        ))
    )

    assert result.passed is False
    assert result.statistical_gate is False
    assert "STATISTICAL_GATE_FAILED" in result.reasons


def test_quality_gate_rejects_non_entry_ready_current_state():
    result = TradingPathQualityGateServiceV015.evaluate(**_inputs(current_state="wait"))

    assert result.passed is False
    assert result.current_state_gate is False
    assert "CURRENT_STATE_GATE_FAILED" in result.reasons
