from decimal import Decimal

from edward.domain.execution import ExecutionDecision, ExecutionMode, ExecutionRequest, ExecutionStatus
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine


class Validator:
    def validate(self, request):
        return True, ()


class Adapter:
    def submit(self, request):
        return "broker-1"

    def cancel(self, broker_order_id):
        pass

    def get_status(self, broker_order_id):
        raise AssertionError("not needed")


def request():
    return ExecutionRequest(
        execution_id="exec-1", account_id="ACC", instrument_uid="uid", ticker="AAA",
        decision=ExecutionDecision.BUY, side="BUY", quantity=Decimal("10"),
        order_type="market", execution_ready=True,
    )


def test_autonomous_submission_does_not_enter_user_confirmation_state():
    engine = ExecutionEngine(adapter=Adapter())
    service = ControlledExecutionService(engine, Validator())
    req = request()

    prepared = service.prepare(req)
    assert prepared.status is ExecutionStatus.READY

    submitted = service.autonomous_submit(req)

    assert submitted.status is ExecutionStatus.SUBMITTED
    assert engine.journal.get("exec-1").status is ExecutionStatus.SUBMITTED


def test_user_confirmation_path_remains_separate():
    engine = ExecutionEngine(adapter=Adapter())
    service = ControlledExecutionService(engine, Validator())
    req = request()
    service.prepare(req)

    waiting = service.request_confirmation(req)
    assert waiting.status is ExecutionStatus.WAITING_CONFIRMATION
    submitted = service.confirm_and_submit(req)
    assert submitted.status is ExecutionStatus.SUBMITTED
