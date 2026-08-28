from decimal import Decimal

import pytest

from edward.domain.execution import ExecutionDecision, ExecutionEventType, ExecutionRequest, ExecutionStatus
from edward.services.execution_engine import ExecutionEngine


class FakeAdapter:
    def __init__(self):
        self.submitted = []
        self.cancelled = []
        self.status = None

    def submit(self, request):
        self.submitted.append(request)
        return "order-1"

    def cancel(self, broker_order_id):
        self.cancelled.append(broker_order_id)

    def get_status(self, broker_order_id):
        return self.status


def request(*, ready=True, execution_id="exec-1"):
    return ExecutionRequest(
        execution_id=execution_id,
        account_id="account-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=Decimal("100"),
        order_type="LIMIT",
        entry_price=Decimal("100"),
        execution_ready=ready,
    )


def test_engine_moves_from_created_to_ready_to_confirmation():
    events = []
    engine = ExecutionEngine(event_callback=events.append)
    req = request()

    assert engine.create(req).status == ExecutionStatus.CREATED
    assert engine.validate(req).status == ExecutionStatus.READY
    assert engine.require_confirmation(req).status == ExecutionStatus.WAITING_CONFIRMATION

    assert [event.event_type for event in events] == [
        ExecutionEventType.CREATED,
        ExecutionEventType.VALIDATION_STARTED,
        ExecutionEventType.VALIDATION_PASSED,
        ExecutionEventType.CONFIRMATION_REQUIRED,
    ]


def test_engine_blocks_request_when_execution_readiness_is_false():
    engine = ExecutionEngine()
    req = request(ready=False)
    engine.create(req)

    result = engine.validate(req)

    assert result.status == ExecutionStatus.BLOCKED
    assert result.error_code == "EXECUTION_NOT_READY"


def test_engine_requires_confirmation_before_submission():
    engine = ExecutionEngine(adapter=FakeAdapter())
    req = request()
    engine.create(req)
    engine.validate(req)

    with pytest.raises(ValueError, match="submission is not allowed"):
        engine.submit(req)


def test_engine_submits_only_after_user_confirmation():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter=adapter)
    req = request()
    engine.create(req)
    engine.validate(req)
    engine.require_confirmation(req)
    engine.confirm(req)

    result = engine.submit(req)

    assert result.status == ExecutionStatus.SUBMITTED
    assert result.broker_order_id == "order-1"
    assert len(adapter.submitted) == 1


def test_engine_rejects_non_confirmation_modes_in_v06_2():
    engine = ExecutionEngine(adapter=FakeAdapter())
    req = request()
    engine.create(req)
    engine.validate(req)
    engine.require_confirmation(req)

    with pytest.raises(ValueError, match="unsupported execution mode"):
        engine.submit(req, mode="prepare_order")


def test_engine_prevents_duplicate_execution_id():
    engine = ExecutionEngine()
    req = request()
    engine.create(req)

    with pytest.raises(ValueError, match="execution_id already exists"):
        engine.create(req)


def test_engine_tracks_failed_submission():
    class BrokenAdapter(FakeAdapter):
        def submit(self, request):
            raise RuntimeError("broker unavailable")

    engine = ExecutionEngine(adapter=BrokenAdapter())
    req = request()
    engine.create(req)
    engine.validate(req)
    engine.require_confirmation(req)

    result = engine.submit(req)

    assert result.status == ExecutionStatus.FAILED
    assert result.error_code == "RuntimeError"


def test_engine_cancel_updates_state():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter=adapter)
    req = request()
    engine.create(req)
    engine.validate(req)
    engine.require_confirmation(req)
    engine.confirm(req)
    engine.submit(req)

    result = engine.cancel(req.execution_id)

    assert result.status == ExecutionStatus.CANCELLED
    assert adapter.cancelled == ["order-1"]
