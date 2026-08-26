from __future__ import annotations

import threading
import time
from decimal import Decimal

import pytest

from edward.domain.execution import ExecutionDecision, ExecutionRequest, ExecutionResult, ExecutionStatus
from edward.services.execution_bridge_service_v06 import ExecutionQueueItem
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


class SlowService:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.thread_id = None

    def confirm_and_submit(self, request):
        self.thread_id = threading.get_ident()
        self.started.set()
        self.release.wait(timeout=2)
        return ExecutionResult(request.execution_id, ExecutionStatus.SUBMITTED, broker_order_id="broker-async")


class FailingService(SlowService):
    def confirm_and_submit(self, request):
        self.thread_id = threading.get_ident()
        self.started.set()
        self.release.wait(timeout=2)
        raise RuntimeError("sandbox submit failed")


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


def _waiting_confirmation_controller(service_instance):
    controller = ExecutionCenterController(service_instance)
    controller.load_request(request())
    controller.state = controller.state.__class__(
        request=controller.state.request,
        result=ExecutionResult("ex-center-1", ExecutionStatus.WAITING_CONFIRMATION),
        status=ExecutionStatus.WAITING_CONFIRMATION,
    )
    return controller


def test_controller_requires_request_before_action():
    controller = ExecutionCenterController(service())
    with pytest.raises(RuntimeError, match="execution request is not loaded"):
        controller.prepare()
    controller.close()


def test_controller_runs_confirmed_flow():
    controller = ExecutionCenterController(service())
    controller.load_request(request())

    assert controller.prepare().status is ExecutionStatus.READY
    assert controller.request_confirmation().status is ExecutionStatus.WAITING_CONFIRMATION
    assert controller.confirm_and_submit().status is ExecutionStatus.SUBMITTED
    assert controller.state.status is ExecutionStatus.SUBMITTED
    controller.close()


def test_controller_does_not_accept_two_active_requests():
    controller = ExecutionCenterController(service())
    controller.load_request(request())
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
    controller.close()


def test_controller_restores_queued_item_without_resetting_status():
    controller = ExecutionCenterController(service())
    queued_request = request()
    queued_result = ExecutionResult(
        execution_id=queued_request.execution_id,
        status=ExecutionStatus.CREATED,
    )

    state = controller.load_queue_item(ExecutionQueueItem(request=queued_request, result=queued_result))

    assert state.request == queued_request
    assert state.result == queued_result
    assert state.status is ExecutionStatus.CREATED
    assert controller.state.request == queued_request
    controller.close()


def test_controller_ignores_loading_the_same_queued_item_again():
    calls = []
    controller = ExecutionCenterController(service(), on_change=lambda state: calls.append(state))
    queued_request = request()
    queued_result = ExecutionResult(
        execution_id=queued_request.execution_id,
        status=ExecutionStatus.CREATED,
    )
    item = ExecutionQueueItem(request=queued_request, result=queued_result)

    controller.load_queue_item(item)
    initial_state = controller.state
    initial_calls = len(calls)

    state = controller.load_queue_item(item)

    assert state is initial_state
    assert controller.state is initial_state
    assert len(calls) == initial_calls
    controller.close()


def test_confirm_and_submit_async_does_not_block_caller():
    service = SlowService()
    published = []
    controller = ExecutionCenterController(
        service,  # type: ignore[arg-type]
        on_change=lambda state: published.append((state.status, state.busy)),
    )
    controller.load_request(request())
    controller.state = controller.state.__class__(
        request=controller.state.request,
        result=ExecutionResult("ex-center-1", ExecutionStatus.WAITING_CONFIRMATION),
        status=ExecutionStatus.WAITING_CONFIRMATION,
    )

    started_at = time.monotonic()
    future = controller.confirm_and_submit_async()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.2
    assert service.started.wait(timeout=1)
    assert controller.state.busy is True

    service.release.set()
    result = future.result(timeout=2)
    deadline = time.monotonic() + 2
    while controller.state.busy and time.monotonic() < deadline:
        time.sleep(0.01)

    assert result.status is ExecutionStatus.SUBMITTED
    assert controller.state.status is ExecutionStatus.SUBMITTED
    assert controller.state.busy is False
    assert controller.state.error is None
    assert published[-1] == (ExecutionStatus.SUBMITTED, False)
    assert service.thread_id is not None
    assert service.thread_id != threading.get_ident()
    controller.close()


def test_confirm_and_submit_async_rejects_duplicate_operation():
    service = SlowService()
    controller = _waiting_confirmation_controller(service)

    first = controller.confirm_and_submit_async()
    assert service.started.wait(timeout=1)
    with pytest.raises(RuntimeError, match="execution operation is already running"):
        controller.confirm_and_submit_async()

    service.release.set()
    assert first.result(timeout=2).status is ExecutionStatus.SUBMITTED
    controller.close()


def test_confirm_and_submit_async_reports_worker_error():
    service = FailingService()
    controller = _waiting_confirmation_controller(service)

    future = controller.confirm_and_submit_async()
    assert service.started.wait(timeout=1)
    service.release.set()

    with pytest.raises(RuntimeError, match="sandbox submit failed"):
        future.result(timeout=2)

    deadline = time.monotonic() + 2
    while controller.state.busy and time.monotonic() < deadline:
        time.sleep(0.01)

    assert controller.state.status is ExecutionStatus.FAILED
    assert controller.state.busy is False
    assert controller.state.error == "sandbox submit failed"
    controller.close()


def test_async_publish_uses_ui_dispatcher():
    service = SlowService()
    dispatched = []

    def dispatch(callback, state):
        dispatched.append((callback, state))

    controller = ExecutionCenterController(service, dispatch=dispatch)
    controller.load_request(request())
    assert dispatched[-1][1].request == request()

    controller.state = controller.state.__class__(
        request=controller.state.request,
        result=ExecutionResult("ex-center-1", ExecutionStatus.WAITING_CONFIRMATION),
        status=ExecutionStatus.WAITING_CONFIRMATION,
    )
    future = controller.confirm_and_submit_async()
    assert service.started.wait(timeout=1)
    assert dispatched[-1][1].busy is True

    service.release.set()
    assert future.result(timeout=2).status is ExecutionStatus.SUBMITTED
    deadline = time.monotonic() + 2
    while controller.state.busy and time.monotonic() < deadline:
        time.sleep(0.01)

    assert dispatched[-1][1].busy is False
    assert dispatched[-1][1].status is ExecutionStatus.SUBMITTED
    controller.close()
