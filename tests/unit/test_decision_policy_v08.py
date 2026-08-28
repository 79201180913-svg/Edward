from types import SimpleNamespace

from edward.services.decision_engine import Decision, OpportunityContext
from edward.services.decision_policy_v08 import DecisionPolicyV08
from edward.services.expected_value_engine_v08 import ExpectedValueEngine
from edward.services.opportunity_engine import OpportunityResult


def _strategy(*, quality_gate: bool = True, score: float = 80.0):
    return SimpleNamespace(strategy="Trend Following", score=score, quality_gate=quality_gate)


def _opportunity(*, score: float = 80.0, entry_ok: bool = True, risk_ok: bool = True, market_ok: bool = True, critical: bool = False):
    context = OpportunityContext(
        opportunity_score=score,
        entry_ok=entry_ok,
        risk_ok=risk_ok,
        strategy_ok=True,
        market_regime_compatible=market_ok,
        critical_risk=critical,
    )
    return OpportunityResult(context, score, entry_ok, market_ok, "test", None)


def _ev(values):
    return ExpectedValueEngine.from_returns(values)


def test_new_position_with_failed_quality_gate_is_pass_not_hold():
    result = DecisionPolicyV08().evaluate_new_position(
        strategy=_strategy(quality_gate=False),
        expected_value=_ev([5, -1, 4]),
        opportunity=_opportunity(score=90),
        confidence_score=90,
        entry_ok=True,
        market_ok=True,
        risk_ok=True,
    )

    assert result.decision is Decision.PASS
    assert result.reason_codes == ("STRATEGY_QUALITY_FAIL",)


def test_new_position_with_positive_but_unreliable_ev_is_wait():
    result = DecisionPolicyV08().evaluate_new_position(
        strategy=_strategy(quality_gate=True),
        expected_value=_ev([8, -2, 7]),
        opportunity=_opportunity(score=90),
        confidence_score=40,
        entry_ok=True,
        market_ok=True,
        risk_ok=True,
    )

    assert result.decision is Decision.WAIT
    assert result.reason_codes == ("EDGE_NOT_RELIABLE",)


def test_existing_position_positive_ev_quality_fail_is_hold():
    result = DecisionPolicyV08().evaluate_existing_position(
        strategy=_strategy(quality_gate=False),
        expected_value=_ev([10, -2, 9, -1]),
        opportunity=_opportunity(score=55),
        confidence_score=40,
        entry_ok=True,
        market_ok=True,
        risk_ok=True,
    )

    assert result.decision is Decision.HOLD
    assert result.reason_codes == ("EDGE_NOT_RELIABLE",)


def test_existing_position_negative_ev_confirmed_by_ci_is_reduce():
    result = DecisionPolicyV08().evaluate_existing_position(
        strategy=_strategy(quality_gate=True),
        expected_value=_ev([-4, -5, -3, -6, -4, -5, -4, -6, -5, -4]),
        opportunity=_opportunity(score=55),
        confidence_score=60,
        entry_ok=True,
        market_ok=True,
        risk_ok=True,
    )

    assert result.decision is Decision.REDUCE
    assert result.reason_codes == ("NEGATIVE_EV_CONFIRMED",)


def test_existing_position_negative_ev_crossing_zero_ci_is_hold():
    result = DecisionPolicyV08().evaluate_existing_position(
        strategy=_strategy(quality_gate=True),
        expected_value=_ev([-10, 8]),
        opportunity=_opportunity(score=55),
        confidence_score=40,
        entry_ok=True,
        market_ok=True,
        risk_ok=True,
    )

    assert result.decision is Decision.HOLD
    assert result.reason_codes == ("NEGATIVE_EV_UNCERTAIN",)
