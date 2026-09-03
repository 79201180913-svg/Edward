from types import SimpleNamespace

from edward.services.trading_path_decision_service_v012 import TradingPathDecisionServiceV012


def _analysis(*, score=80.0, confidence=80.0, risk_gate=True, validation_status="validated"):
    return SimpleNamespace(
        evidence=SimpleNamespace(),
        validation=SimpleNamespace(promotion_status=validation_status),
        opportunity=SimpleNamespace(
            risk_gate=risk_gate,
            expected_value_pct=1.0,
            score=score,
            confidence=confidence,
        ),
    )


def test_decision_engine_preserves_buy_wait_pass_semantics():
    buy = TradingPathDecisionServiceV012.decide(_analysis())
    wait = TradingPathDecisionServiceV012.decide(_analysis(score=60.0, confidence=80.0))
    passed = TradingPathDecisionServiceV012.decide(_analysis(risk_gate=False))

    assert buy.decision.value == "buy"
    assert buy.current_state.value == "entry_ready"
    assert buy.status.value == "promotable"

    assert wait.decision.value == "wait"
    assert wait.current_state.value == "wait"
    assert wait.status.value == "validated"
    assert "OPPORTUNITY_SCORE_BELOW_THRESHOLD" in wait.reasons

    assert passed.decision.value == "pass"
    assert passed.current_state.value == "invalid"
    assert passed.status.value == "rejected"
    assert "RISK_GATE_FAILED" in passed.reasons


def test_low_confidence_is_wait_not_pass():
    result = TradingPathDecisionServiceV012.decide(_analysis(confidence=50.0))

    assert result.decision.value == "wait"
    assert result.current_state.value == "wait"
    assert result.status.value == "validated"
    assert "CONFIDENCE_BELOW_THRESHOLD" in result.reasons
