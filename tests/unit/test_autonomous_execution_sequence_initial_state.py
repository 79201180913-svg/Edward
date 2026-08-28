from decimal import Decimal
from types import SimpleNamespace

from edward.domain.execution import ExecutionMode, ExecutionStatus
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_sequence_service import AutonomousExecutionSequenceService


class FakeBridge:
    def __init__(self):
        self.intake = SimpleNamespace(confirmation_service=SimpleNamespace())
        self.counter = 0

    def autonomous_submit(self, execution_id):
        return SimpleNamespace(execution_id=execution_id, status=ExecutionStatus.FILLED, filled_quantity=10, error_message=None)


class FakeRefresh:
    def __init__(self, state):
        self.state = state
        self.calls = 0

    def refresh(self, account_id):
        self.calls += 1
        return self.state


class FakeStepService:
    def prepare_step(self, *, account_id, step, result, dependency_completed):
        return SimpleNamespace(accepted=True, request=SimpleNamespace(execution_id="exec-1", quantity=Decimal("10")), result=SimpleNamespace(status=ExecutionStatus.READY), reason="")


class FakeVerifier:
    def verify(self, **kwargs):
        return SimpleNamespace(passed=True, reasons=())


def test_initial_state_is_used_without_pre_execution_refresh():
    bridge = FakeBridge()
    refresh = FakeRefresh(AccountState(portfolio=None, positions=[], balance=None, orders=[]))
    service = AutonomousExecutionSequenceService(bridge, refresh, step_service=FakeStepService(), verifier=FakeVerifier())
    plan = AutonomousExecutionPlan(steps=(ExecutionPlanStep(sequence=1, action="BUY", ticker="NEW", instrument_uid="new", target_value=Decimal("10000"), depends_on=None),))

    outcome = service.execute_confirmed_plan(
        account_id="ACC", plan=plan, result_factory=lambda step: SimpleNamespace(recommended_quantity=10),
        mode=ExecutionMode.AUTONOMOUS,
        initial_state=AccountState(portfolio=None, positions=[], balance=None, orders=[]),
    )

    assert outcome.completed is True
    assert refresh.calls == 1
