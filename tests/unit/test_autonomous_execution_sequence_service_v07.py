from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from edward.domain.execution import ExecutionMode, ExecutionStatus
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_sequence_service import AutonomousExecutionPhase, AutonomousExecutionSequenceService


class FakeRefresh:
    def refresh(self, account_id):
        return SimpleNamespace(positions=())


class FakeSteps:
    def prepare_step(self, *, account_id, step, result, dependency_completed=True):
        return SimpleNamespace(accepted=True, request=SimpleNamespace(execution_id=f"exec-{step.sequence}"), result=None, reason="")


class FakeBridge:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.submitted = []
        self.waited = []

    def autonomous_submit(self, execution_id):
        self.submitted.append(execution_id)
        sequence = int(execution_id.split("-")[-1])
        if sequence in self.failures:
            return SimpleNamespace(status=ExecutionStatus.FAILED, filled_quantity=0, error_message="broker rejected")
        return SimpleNamespace(status=ExecutionStatus.SUBMITTED, filled_quantity=0, error_message="", broker_order_id=execution_id)

    def wait_for_terminal(self, execution_id, *, timeout_seconds, poll_interval_seconds):
        self.waited.append(execution_id)
        return SimpleNamespace(status=ExecutionStatus.FILLED, filled_quantity=1, error_message="", broker_order_id=execution_id)


class FakeVerifier:
    def verify(self, *, step, state, expected_quantity, before_quantity):
        return SimpleNamespace(passed=True, reasons=())


def _plan(*steps):
    return AutonomousExecutionPlan(steps=tuple(steps))


def _step(sequence, action="BUY", depends_on=None):
    return ExecutionPlanStep(
        sequence=sequence,
        action=action,
        ticker=f"T{sequence}",
        instrument_uid=f"uid-{sequence}",
        target_value=Decimal("100.00"),
        depends_on=depends_on,
    )


def _result_factory(step):
    return SimpleNamespace(
        decision=step.action,
        execution_ready=True,
        instrument_uid=step.instrument_uid,
        ticker=step.ticker,
        recommended_quantity=1,
        price=100.0,
    )


def test_failed_step_does_not_stop_independent_steps():
    bridge = FakeBridge(failures={1})
    service = AutonomousExecutionSequenceService(bridge, FakeRefresh(), step_service=FakeSteps(), verifier=FakeVerifier())
    result = service.execute_confirmed_plan(account_id="acc", plan=_plan(_step(1), _step(2)), result_factory=_result_factory, mode=ExecutionMode.AUTONOMOUS)
    assert [step.step.sequence for step in result.steps] == [1, 2]
    assert result.steps[0].completed is False
    assert result.steps[1].completed is True
    assert len(result.executed_steps) == 2
    assert len(result.failed_steps) == 1
    assert result.completed is False
    assert result.phase is AutonomousExecutionPhase.FAILED
    assert bridge.submitted == ["exec-1", "exec-2"]
    assert bridge.waited == ["exec-2"]


def test_failed_dependency_is_skipped_but_later_independent_step_runs():
    bridge = FakeBridge(failures={1})
    service = AutonomousExecutionSequenceService(bridge, FakeRefresh(), step_service=FakeSteps(), verifier=FakeVerifier())
    result = service.execute_confirmed_plan(account_id="acc", plan=_plan(_step(1), _step(2, depends_on=1), _step(3)), result_factory=_result_factory, mode=ExecutionMode.AUTONOMOUS)
    assert [step.step.sequence for step in result.steps] == [1, 2, 3]
    assert result.steps[1].reason == "DEPENDENCY_NOT_COMPLETED:1"
    assert result.steps[1].execution_id is None
    assert result.steps[2].completed is True
    assert bridge.submitted == ["exec-1", "exec-3"]
    assert bridge.waited == ["exec-3"]
    assert len(result.failed_steps) == 2
    assert result.completed is False


def test_successful_plan_waits_for_fill_before_verification():
    bridge = FakeBridge()
    service = AutonomousExecutionSequenceService(bridge, FakeRefresh(), step_service=FakeSteps(), verifier=FakeVerifier())
    result = service.execute_confirmed_plan(account_id="acc", plan=_plan(_step(1)), result_factory=_result_factory, mode=ExecutionMode.AUTONOMOUS)
    assert result.completed is True
    assert result.phase is AutonomousExecutionPhase.COMPLETED
    assert result.steps[0].status is ExecutionStatus.FILLED
    assert bridge.waited == ["exec-1"]


def test_successful_plan_is_completed():
    bridge = FakeBridge()
    service = AutonomousExecutionSequenceService(bridge, FakeRefresh(), step_service=FakeSteps(), verifier=FakeVerifier())
    result = service.execute_confirmed_plan(account_id="acc", plan=_plan(_step(1), _step(2)), result_factory=_result_factory, mode=ExecutionMode.AUTONOMOUS)
    assert result.completed is True
    assert result.phase is AutonomousExecutionPhase.COMPLETED
    assert len(result.executed_steps) == 2
    assert len(result.failed_steps) == 0
