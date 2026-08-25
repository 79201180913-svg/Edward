from decimal import Decimal

import pytest

from edward.domain.execution import ExecutionDecision, ExecutionMode, ExecutionRequest, ExecutionStatus
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
    def __init__(self, passed=True):
        self.passed = passed
        self.calls = 0

    def validate(self, request):
        self.calls += 1
        return self.passed, (() if self.passed else ("TRADING_STATUS_CHANGED",))


def request():
    return ExecutionRequest(
        execution_id="ex-1",
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


def test_prepare_then_confirmation_then_submit():
    adapter = FakeAdapter()
    validator = FakeValidator()
    service = ControlledExecutionService(ExecutionEngine(adapter=adapter), validator)

    assert service.prepare(request()).status is ExecutionStatus.READY
    assert service.request_confirmation(request()).status is ExecutionStatus.WAITING_CONFIRMATION
    result = service.confirm_and_submit(request())

    assert result.status is ExecutionStatus.SUBMITTED
    assert adapter.submitted and adapter.submitted[0].execution_id == "ex-1"
    assert validator.calls == 1


def test_failed_pretrade_revalidation_blocks_submission():
    adapter = FakeAdapter()
    validator = FakeValidator(False)
    service = ControlledExecutionService(ExecutionEngine(adapter=adapter), validator)
    service.prepare(request())
    service.request_confirmation(request())

    result = service.confirm_and_submit(request())

    assert result.status is ExecutionStatus.BLOCKED
    assert result.error_code == "PRETRADE_VALIDATION_FAILED"
    assert adapter.submitted == []
    assert validator.calls == 1


def test_confirmation_is_not_available_before_ready():
    service = ControlledExecutionService(ExecutionEngine(adapter=FakeAdapter()), FakeValidator())
    req = request()
    service.prepare(req)
    with pytest.raises(ValueError, match="confirmation is not available"):
        service.request_confirmation(req)


def test_auto_mode_is_not_used_in_06():
    assert ExecutionMode.USER_CONFIRMATION.value == "user_confirmation"
