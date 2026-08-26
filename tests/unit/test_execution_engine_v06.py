from types import SimpleNamespace

import pytest

from edward.domain.execution import ExecutionDecision, ExecutionEngine, ExecutionMode, ExecutionRequest, ExecutionStatus


class FakeAdapter:
    def __init__(self):
        self.submitted = []

    def submit(self, request):
        self.submitted.append(request)
        return "order-1"

    def cancel(self, broker_order_id):
        pass

    def get_status(self, broker_order_id):
        return SimpleNamespace(
            execution_id="exec-1",
            status=ExecutionStatus.FILLED,
            broker_order_id=broker_order_id,
        )


def request():
    return ExecutionRequest(
        execution_id="exec-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=1,
        order_type="market",
        execution_ready=True,
    )


def test_engine_submit_user_confirmation_mode():
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
        engine.submit(req, mode=ExecutionMode.PREPARE_ORDER)


def test_engine_prevents_duplicate_execution_id():
    engine = ExecutionEngine()
    req = request()
    engine.create(req)

    with pytest.raises(ValueError, match="execution_id already exists"):
        engine.create(req)


def test_engine_tracks_failed_submission():
    class FailingAdapter(FakeAdapter):
        def submit(self, request):
            raise RuntimeError("broker unavailable")

    engine = ExecutionEngine(adapter=FailingAdapter())
    req = request()
    engine.create(req)
    engine.validate(req)
    engine.require_confirmation(req)
    engine.confirm(req)

    result = engine.submit(req)

    assert result.status == ExecutionStatus.FAILED
    assert result.error_code == "RuntimeError"
