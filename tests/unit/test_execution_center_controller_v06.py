from decimal import Decimal

import pytest

from edward.domain.execution import ExecutionDecision, ExecutionRequest, ExecutionStatus
from edward.services.execution_center_controller_v06 import ExecutionCenterController
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine


class FakeAdapter:
    def __init__(self):
        self.submitted = []

    def submit(self, request):
        self.submitted.append(request)
        return "broker-1"

    def cancel(self, broker_order_id):
        pass

    def get_status(self, broker_order_id):
        raise AssertionError("not used")


class FakeValidator:
    def validate(self, request):
        return True, ()


def request():
    return ExecutionRequest(
        execution_id="ex-center-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=Decimal("10"),
        order_type="LIMIT",
        entry_price=Decimal("100"),
        execution_ready=True,
    )


def service():
    return ControlledExecutionService(
        ExecutionEngine(adapter=FakeAdapter()),
        FakeValidator(),
    )


def test_controller_requires_request_before_action():
    controller = ExecutionCenterController(service())
    with pytest.raises(RuntimeError, match="execution request is not loaded"):
        controller.prepare()


def test_controller_runs_confirmed_flow():
    controller = ExecutionCenterController(service())
    controller.load_request(request())

    assert controller.prepare().status is ExecutionStatus.READY
    assert controller.request_confirmation().status is ExecutionStatus.WAITING_CONFIRMATION
    assert controller.confirm_and_submit().status is ExecutionStatus.SUBMITTED
    assert controller.state.status is ExecutionStatus.SUBMITTED


def test_controller_does_not_accept_two_active_requests():
    controller = ExecutionCenterController(service())
    controller.load_request(request())
    second = request()
    second = ExecutionRequest(
        execution_id="ex-center-2",
        account_id="acc-1",
        instrument_uid="uid-2",
        ticker="TEST2",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=Decimal("1"),
        order_type="LIMIT",
        entry_price=Decimal("10"),
        execution_ready=True,
    )
    with pytest.raises(ValueError, match="another execution is already active"):
        controller.load_request(second)
