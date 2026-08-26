from decimal import Decimal
from types import SimpleNamespace

from edward.domain.execution import ExecutionStatus
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_sequence_service import (
    AutonomousExecutionPhase,
    AutonomousExecutionSequenceService,
)


class FakeConfirmation:
    def __init__(self, submitted_status=ExecutionStatus.FILLED):
        self.submitted_status = submitted_status
        self.submitted = []

    def confirm_and_submit(self, request):
        self.submitted.append(request.execution_id)
        return SimpleNamespace(
            execution_id=request.execution_id,
            status=self.submitted_status,
            filled_quantity=request.quantity,
            error_message=None,
        )


class FakeBridge:
    def __init__(self, confirmation):
        self.confirmation_service = confirmation
        self.intake = SimpleNamespace(confirmation_service=confirmation)
        self.counter = 0

    def enqueue_opportunity(self, *, account_id, result):
        self.counter += 1
        request = SimpleNamespace(execution_id=f"exec-{self.counter}", quantity=Decimal(str(result.recommended_quantity)))
        return SimpleNamespace(accepted=True, request=request, result=SimpleNamespace(status=ExecutionStatus.READY), reason="")

    def request_confirmation(self, execution_id):
        return SimpleNamespace(status=ExecutionStatus.WAITING_CONFIRMATION)


class FakeRefresh:
    def __init__(self, *states):
        self.states = list(states)

    def refresh(self, account_id):
        return self.states.pop(0)


def state(uid="old", quantity=10):
    return AccountState(portfolio=None, positions=[SimpleNamespace(instrument_uid=uid, quantity=quantity)], balance=None, orders=None)


def step(sequence, action, uid, ticker, depends_on=None):
    return ExecutionPlanStep(sequence=sequence, action=action, ticker=ticker, instrument_uid=uid, target_value=Decimal("10000"), depends_on=depends_on)


def result(step):
    return SimpleNamespace(decision=step.action, execution_ready=True, instrument_uid=step.instrument_uid, ticker=step.ticker, recommended_quantity=10, price=100)


def test_replace_sequence_stops_before_buy_when_sell_not_verified():
    confirmation = FakeConfirmation()
    service = AutonomousExecutionSequenceService(FakeBridge(confirmation), FakeRefresh(state("old", 10), state("old", 2)))
    plan = AutonomousExecutionPlan(steps=(step(1, "SELL", "old", "OLD"), step(2, "BUY", "new", "NEW", depends_on=1)))

    outcome = service.execute_confirmed_plan(account_id="ACC", plan=plan, result_factory=result)

    assert outcome.completed is False
    assert outcome.stopped_at == 1
    assert outcome.phase is AutonomousExecutionPhase.STOPPED
    assert [event.phase for event in outcome.events] == [
        AutonomousExecutionPhase.PREPARING,
        AutonomousExecutionPhase.EXECUTING,
        AutonomousExecutionPhase.VERIFYING,
        AutonomousExecutionPhase.STOPPED,
    ]
    assert confirmation.submitted == ["exec-1"]


def test_replace_sequence_allows_buy_after_verified_sell():
    confirmation = FakeConfirmation()
    service = AutonomousExecutionSequenceService(
        FakeBridge(confirmation),
        FakeRefresh(state("old", 10), state("old", 0), state("old", 0), state("new", 10)),
    )
    plan = AutonomousExecutionPlan(steps=(step(1, "SELL", "old", "OLD"), step(2, "BUY", "new", "NEW", depends_on=1)))

    outcome = service.execute_confirmed_plan(account_id="ACC", plan=plan, result_factory=result)

    assert outcome.completed is True
    assert outcome.phase is AutonomousExecutionPhase.COMPLETED
    assert [item.step.action for item in outcome.steps] == ["SELL", "BUY"]
    assert confirmation.submitted == ["exec-1", "exec-2"]
    assert outcome.events[-1].phase is AutonomousExecutionPhase.COMPLETED


def test_sequence_stops_when_submission_fails():
    confirmation = FakeConfirmation(ExecutionStatus.BLOCKED)
    service = AutonomousExecutionSequenceService(FakeBridge(confirmation), FakeRefresh(state("old", 10), state("old", 10)))
    plan = AutonomousExecutionPlan(steps=(step(1, "SELL", "old", "OLD"),))

    outcome = service.execute_confirmed_plan(account_id="ACC", plan=plan, result_factory=result)

    assert outcome.completed is False
    assert outcome.stopped_at == 1
    assert outcome.phase is AutonomousExecutionPhase.STOPPED
    assert outcome.steps[0].verification is None


def test_dependency_failure_is_reported_as_stopped_phase():
    confirmation = FakeConfirmation()
    service = AutonomousExecutionSequenceService(FakeBridge(confirmation), FakeRefresh(state("old", 0)))
    plan = AutonomousExecutionPlan(steps=(step(1, "BUY", "new", "NEW", depends_on=99),))

    outcome = service.execute_confirmed_plan(account_id="ACC", plan=plan, result_factory=result)

    assert outcome.completed is False
    assert outcome.phase is AutonomousExecutionPhase.STOPPED
    assert outcome.steps[0].reason == "DEPENDENCY_NOT_COMPLETED:99"


class FakeProtection:
    def __init__(self):
        self.calls = []

    def protect_fill(self, *, account_id, instrument_uid, quantity, result):
        self.calls.append({"account_id": account_id, "instrument_uid": instrument_uid, "quantity": quantity, "result": result})
        return SimpleNamespace(protected=True, status="PROTECTED", reason="", stop_order_id="stop-1")


def test_buy_fill_is_protected_inside_autonomous_execution_sequence():
    confirmation = FakeConfirmation()
    protection = FakeProtection()
    service = AutonomousExecutionSequenceService(
        FakeBridge(confirmation),
        FakeRefresh(state("new", 0), state("new", 10)),
        protection_service=protection,
    )
    plan = AutonomousExecutionPlan(steps=(step(1, "BUY", "new", "NEW"),))

    outcome = service.execute_confirmed_plan(
        account_id="ACC", plan=plan, result_factory=result,
    )

    assert outcome.completed is True
    assert outcome.steps[0].protection.protected is True
    assert outcome.steps[0].protection.status == "PROTECTED"
    assert outcome.events[-3].phase is AutonomousExecutionPhase.PROTECTED
    assert protection.calls[0]["quantity"] == 10
