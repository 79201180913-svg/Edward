from decimal import Decimal
from types import SimpleNamespace

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_trading_controller import AutonomousTradingController
from edward.services.budget_planning_service import BudgetPlan


class FakeSequence:
    def execute_confirmed_plan(self, **kwargs):
        raise AssertionError("execution must not start when protection gate rejects")


class FakePreflight:
    def validate(self, **kwargs):
        return SimpleNamespace(passed=True, reasons=())


class RejectingProtection:
    def reconcile(self, **kwargs):
        return SimpleNamespace(protected=False, reasons=("ORPHAN_PROTECTION:stop-1",))


def make_plan():
    return AutonomousExecutionPlan(
        steps=(
            ExecutionPlanStep(
                sequence=1,
                action="SELL",
                ticker="TEST",
                instrument_uid="uid-1",
                target_value=Decimal("10000"),
                depends_on=None,
            ),
        )
    )


def make_budget():
    return BudgetPlan(
        account_capital=Decimal("100000"),
        cash=Decimal("100000"),
        blocked_cash=Decimal("0"),
        invested=Decimal("0"),
        reserve=Decimal("10000"),
        planning_budget=Decimal("90000"),
        investable_cash=Decimal("90000"),
        slots=5,
        target_position_value=Decimal("18000"),
    )


def test_replanning_keeps_built_plan_when_preflight_rejects():
    controller = AutonomousTradingController(
        FakeSequence(),
        preflight_service=FakePreflight(),
        protection_reconciliation=RejectingProtection(),
    )
    controller.enable()

    state = AccountState(portfolio={}, positions=[], balance=None, orders=[])
    plan = make_plan()
    built = []

    result = controller.execute_replanned(
        account_id="ACC",
        mode=ExecutionMode.AUTONOMOUS,
        refresh_state=lambda: state,
        build_plan=lambda current: (built.append(current) or plan),
        budget_for_state=lambda current: make_budget(),
        result_factory=lambda step: None,
        max_iterations=1,
    )

    assert built == [state]
    assert result.executed is False
    assert result.reason.startswith("EXECUTION_ERROR:PROTECTION_RECONCILIATION_FAILED")
    assert result.preflight_reasons == ("ORPHAN_PROTECTION:stop-1",)
