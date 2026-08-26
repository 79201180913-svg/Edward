from decimal import Decimal
from types import SimpleNamespace

from edward.domain.execution import ExecutionMode
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_trading_controller import AutonomousTradingController
from edward.services.budget_planning_service import BudgetPlan
from edward.services.protection_reconciliation_service import ProtectionReconciliationResult


class Sequence:
    def __init__(self):
        self.called = False

    def execute_confirmed_plan(self, **kwargs):
        self.called = True
        return SimpleNamespace(completed=True, stopped_at=None, steps=(), phase=None, events=())


class Protection:
    def __init__(self, result):
        self.result = result
        self.called = False

    def reconcile(self, **kwargs):
        self.called = True
        return self.result


def budget():
    return BudgetPlan(account_capital=Decimal("100000"), cash=Decimal("50000"), blocked_cash=Decimal("0"), invested=Decimal("50000"), reserve=Decimal("10000"), planning_budget=Decimal("90000"), investable_cash=Decimal("40000"), slots=5, target_position_value=Decimal("18000"))


def state():
    return SimpleNamespace(account_id=None, positions=[{"instrument_uid": "uid", "quantity": 10}], portfolio=None, balance=None, orders=[])


def plan():
    return AutonomousExecutionPlan(steps=(SimpleNamespace(sequence=1, depends_on=None, instrument_uid="uid", action="HOLD", target_value=Decimal("0")),))


def test_blocks_autonomous_execution_when_protection_reconciliation_fails():
    sequence = Sequence()
    protection = Protection(ProtectionReconciliationResult("RECONCILIATION_ERROR", False, ("PROTECTION_REQUIRED:uid",)))
    controller = AutonomousTradingController(sequence, protection_reconciliation=protection)
    controller.enable()

    result = controller.execute(account_id="ACC", plan=plan(), result_factory=lambda step: step, mode=ExecutionMode.AUTONOMOUS, budget=budget(), state=state())

    assert result.executed is False
    assert result.reason == "PROTECTION_RECONCILIATION_FAILED"
    assert result.preflight_reasons == ("PROTECTION_REQUIRED:uid",)
    assert protection.called is True
    assert sequence.called is False


def test_allows_autonomous_execution_when_protection_reconciliation_passes():
    sequence = Sequence()
    protection = Protection(ProtectionReconciliationResult("PROTECTED", True))
    controller = AutonomousTradingController(sequence, protection_reconciliation=protection)
    controller.enable()

    result = controller.execute(account_id="ACC", plan=plan(), result_factory=lambda step: step, mode=ExecutionMode.AUTONOMOUS, budget=budget(), state=state())

    assert result.executed is True
    assert result.reason == "COMPLETED"
    assert sequence.called is True
