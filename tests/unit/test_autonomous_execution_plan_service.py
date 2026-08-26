from decimal import Decimal
from types import SimpleNamespace

from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlanService


def make(action, ticker, uid, source_ticker=None, source_uid=None):
    return SimpleNamespace(
        action=action,
        ticker=ticker,
        instrument_uid=uid,
        score=90.0,
        risk_score=10.0,
        target_value=Decimal("10000"),
        source_ticker=source_ticker,
        source_instrument_uid=source_uid,
        reason="test",
    )


def test_replace_becomes_sell_then_buy():
    plan = AutonomousExecutionPlanService().build(
        [make("REPLACE", "NEW", "new", "OLD", "old")]
    )
    assert [x.action for x in plan.steps] == ["SELL", "BUY"]
    assert plan.steps[0].ticker == "OLD"
    assert plan.steps[1].ticker == "NEW"
    assert plan.steps[1].depends_on == plan.steps[0].sequence
    assert plan.executable is False
    assert plan.requires_user_confirmation is True


def test_sell_and_reduce_precede_buys():
    plan = AutonomousExecutionPlanService().build(
        [make("BUY", "NEW", "new"), make("SELL", "OLD", "old"), make("REDUCE", "TRIM", "trim"), make("ADD", "ADDME", "add")]
    )
    assert [x.action for x in plan.steps] == ["SELL", "REDUCE", "BUY", "ADD"]


def test_hold_is_not_executable_step():
    plan = AutonomousExecutionPlanService().build([make("HOLD", "KEEP", "keep")])
    assert plan.steps == ()
