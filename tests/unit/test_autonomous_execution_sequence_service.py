from decimal import Decimal
from types import SimpleNamespace

from edward.domain.execution import ExecutionStatus
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import (
    AutonomousExecutionPlan,
    ExecutionPlanStep,
)
from edward.services.autonomous_execution_sequence_service import (
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
        request = SimpleNamespace(
            execution_id=f"exec-{self.counter}",
            quantity=Decimal(str(result.recommended_quantity)),
        )
        return SimpleNamespace(accepted=True, request=request, result=SimpleNamespace(status=ExecutionStatus.READY), reason="")

    def request_confirmation(self, execution_id):
        return SimpleNamespace(status=ExecutionStatus.WAITING_CONFIRMATION)


class FakeRefresh:
    def __init__(self, before, after):
        self.states = [before, after]

    def refresh(self, account_id):
        return self.states.pop(0)


def state(uid="old", quantity=10):
    return AccountState(
        portfolio=None,
        positions=[SimpleNamespace(instrument_uid=uid, quantity=quantity)],
        balance=None,
        orders=None,
    )


def step(sequence, action, uid, ticker, depends_on=None):
    return ExecutionPlanStep(
        sequence=sequence,
        action=action,
        ticker=ticker,
        instrument_uid=uid,
        target_value=Decimal("10000"),
        depends_on=depends_on,
    )


def result(step):
    return SimpleNamespace(
        decision=step.action,
        execution_ready=True,
        instrument_uid=step.instrument_uid,
        ticker=step.ticker,
        recommended_quantity=10,
        price=100,
    )


def test_replace_sequence_stops_before_buy_when_sell_not_verified():
    confirmation = FakeConfirmation()
    bridge = FakeBridge(confirmation)
    refresh = FakeRefresh(state("old", 10), state("old", 2))
    service = AutonomousExecutionSequenceService(bridge, refresh)
    plan = AutonomousExecutionPlan(steps=(
        step(1, "SELL", "old", "OLD"),
        step(2, "BUY", "new", "NEW", depends_on=1),
    ))

    outcome = service.execute_confirmed_plan(
        account_id="ACC", plan=plan, result_factory=result,
    )

    assert outcome.completed is False
    assert outcome.stopped_at == 1
    assert len(outcome.steps) == 1
    assert confirmation.submitted == ["exec-1"]


def test_replace_sequence_allows_buy_after_verified_sell():
    confirmation = FakeConfirmation()
    bridge = FakeBridge(confirmation)
    refresh = FakeRefresh(
        state("old", 10),
        state("old", 0),
    )
    # A real second refresh is needed before the BUY and after it.
    refresh.states.extend([state("old", 0), state("new", 10)])
    service = AutonomousExecutionSequenceService(bridge, refresh)
    plan = AutonomousExecutionPlan(steps=(
        step(1, "SELL", "old", "OLD"),
        step(2, "BUY", "new", "NEW", depends_on=1),
    ))

    outcome = service.execute_confirmed_plan(
        account_id="ACC", plan=plan, result_factory=result,
    )

    assert outcome.completed is True
    assert [item.step.action for item in outcome.steps] == ["SELL", "BUY"]
    assert confirmation.submitted == ["exec-1", "exec-2"]


def test_sequence_stops_when_submission_fails():
    confirmation = FakeConfirmation(ExecutionStatus.BLOCKED)
    bridge = FakeBridge(confirmation)
    refresh = FakeRefresh(state("old", 10), state("old", 10))
    service = AutonomousExecutionSequenceService(bridge, refresh)
    plan = AutonomousExecutionPlan(steps=(step(1, "SELL", "old", "OLD"),))

    outcome = service.execute_confirmed_plan(
        account_id="ACC", plan=plan, result_factory=result,
    )

    assert outcome.completed is False
    assert outcome.stopped_at == 1
    assert outcome.steps[0].verification is None
