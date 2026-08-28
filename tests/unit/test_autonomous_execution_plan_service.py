from decimal import Decimal
from types import SimpleNamespace

from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlanService


def make(action, ticker, uid, source_ticker=None, source_uid=None):
    return SimpleNamespace(action=action, ticker=ticker, instrument_uid=uid, score=90.0, risk_score=10.0, target_value=Decimal("10000"), source_ticker=source_ticker, source_instrument_uid=source_uid, reason="test")


def test_replace_becomes_sell_then_buy_with_dependency():
    plan = AutonomousExecutionPlanService().build([make("REPLACE", "NEW", "new", "OLD", "old")])
    assert [x.action for x in plan.steps] == ["SELL", "BUY"]
    assert plan.steps[0].ticker == "OLD"
    assert plan.steps[1].ticker == "NEW"
    assert plan.steps[1].depends_on == plan.steps[0].sequence
    assert plan.steps[0].requires_revalidation is True
    assert plan.steps[1].requires_revalidation is True
    assert plan.executable is False
    assert plan.requires_user_confirmation is True


def test_sell_and_reduce_precede_buys():
    plan = AutonomousExecutionPlanService().build([make("BUY", "NEW", "new"), make("SELL", "OLD", "old"), make("REDUCE", "TRIM", "trim"), make("ADD", "ADDME", "add")])
    assert [x.action for x in plan.steps] == ["SELL", "REDUCE", "BUY", "ADD"]


def test_hold_is_not_executable_step():
    plan = AutonomousExecutionPlanService().build([make("HOLD", "KEEP", "keep")])
    assert plan.steps == ()


def test_multiple_replacements_have_independent_sell_then_buy_dependencies():
    plan = AutonomousExecutionPlanService().build([
        make("REPLACE", "NEW1", "new1", "OLD1", "old1"),
        make("REPLACE", "NEW2", "new2", "OLD2", "old2"),
    ])
    assert [x.action for x in plan.steps] == ["SELL", "SELL", "BUY", "BUY"]
    assert plan.steps[2].depends_on == plan.steps[0].sequence
    assert plan.steps[3].depends_on == plan.steps[1].sequence
    assert plan.steps[2].source_instrument_uid == "old1"
    assert plan.steps[3].source_instrument_uid == "old2"
