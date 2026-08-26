from decimal import Decimal
from types import SimpleNamespace

from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_preflight_service import AutonomousExecutionPreflightService
from edward.services.budget_planning_service import BudgetPlan


def budget(*, cash="50000", slots=5):
    return BudgetPlan(
        account_capital=Decimal("100000"),
        cash=Decimal(cash),
        blocked_cash=Decimal("0"),
        invested=Decimal("50000"),
        reserve=Decimal("0"),
        planning_budget=Decimal("100000"),
        investable_cash=Decimal(cash),
        slots=slots,
        target_position_value=Decimal("20000"),
    )


def state(uids=("old",), orders=()):
    return AccountState(
        portfolio=None,
        positions=[SimpleNamespace(instrument_uid=uid, quantity=10) for uid in uids],
        balance=None,
        orders=list(orders),
    )


def step(seq, action, uid, value="10000", depends=None):
    return ExecutionPlanStep(
        sequence=seq,
        action=action,
        ticker=uid,
        instrument_uid=uid,
        target_value=Decimal(value),
        depends_on=depends,
    )


def plan(*steps):
    return AutonomousExecutionPlan(steps=tuple(steps))


def test_accepts_fresh_plan_with_available_cash_and_slots():
    result = AutonomousExecutionPreflightService().validate(
        plan=plan(step(1, "SELL", "old"), step(2, "BUY", "new", depends=1)),
        budget=budget(cash="0"),
        state=state(("old",)),
    )
    assert result.passed is True
    assert result.reasons == ()


def test_rejects_buy_when_cash_is_insufficient():
    result = AutonomousExecutionPreflightService().validate(
        plan=plan(step(1, "BUY", "new", value="60000")),
        budget=budget(cash="50000"),
        state=state(("old",)),
    )
    assert result.passed is False
    assert any(reason.startswith("INSUFFICIENT_INVESTABLE_CASH") for reason in result.reasons)


def test_rejects_sell_of_missing_position():
    result = AutonomousExecutionPreflightService().validate(
        plan=plan(step(1, "SELL", "missing")),
        budget=budget(),
        state=state(("old",)),
    )
    assert result.passed is False
    assert "POSITION_NOT_FOUND:1:missing" in result.reasons


def test_rejects_buy_of_already_held_position():
    result = AutonomousExecutionPreflightService().validate(
        plan=plan(step(1, "BUY", "old")),
        budget=budget(),
        state=state(("old",)),
    )
    assert result.passed is False
    assert "BUY_ALREADY_HELD:1:old" in result.reasons


def test_rejects_active_order_conflict():
    order = SimpleNamespace(instrument_uid="new", status="SUBMITTED")
    result = AutonomousExecutionPreflightService().validate(
        plan=plan(step(1, "BUY", "new")),
        budget=budget(),
        state=state(("old",), orders=(order,)),
    )
    assert result.passed is False
    assert "ACTIVE_ORDER_CONFLICT:1:new" in result.reasons


def test_rejects_slot_overflow_after_plan():
    result = AutonomousExecutionPreflightService().validate(
        plan=plan(step(1, "BUY", "new")),
        budget=budget(cash="50000", slots=1),
        state=state(("old",)),
    )
    assert result.passed is False
    assert "SLOT_LIMIT_EXCEEDED:2>1" in result.reasons


def test_rejects_invalid_dependency_order():
    result = AutonomousExecutionPreflightService().validate(
        plan=plan(step(1, "BUY", "new", depends=2), step(2, "SELL", "old")),
        budget=budget(),
        state=state(("old",)),
    )
    assert result.passed is False
    assert "INVALID_DEPENDENCY:1->2" in result.reasons
