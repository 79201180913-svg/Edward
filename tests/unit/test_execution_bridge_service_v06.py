from dataclasses import replace
from decimal import Decimal

import pytest

from edward.domain.execution import ExecutionDecision, ExecutionMode, ExecutionRequest, ExecutionResult, ExecutionStatus
from edward.services.execution_bridge_service_v06 import ExecutionBridgeService
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine


class FakeAdapter:
    def submit(self, request):
        return "broker-1"

    def cancel(self, broker_order_id):
        return None

    def get_status(self, broker_order_id):
        return ExecutionResult("ex-1", ExecutionStatus.SUBMITTED, broker_order_id=broker_order_id)


class ReadyValidator:
    def validate(self, request):
        return request.execution_ready, () if request.execution_ready else ("EXECUTION_NOT_READY",)


def request_result(execution_ready=True):
    plan = type("Plan", (), {"entry_price": 100.0, "stop_price": 95.0})()
    return type(
        "Opportunity",
        (),
        {
            "decision": "BUY",
            "execution_ready": execution_ready,
            "recommended_quantity": 10,
            "instrument_uid": "uid-1",
            "ticker": "TEST",
            "price": 100.0,
            "trade_plan": plan,
            "strategy_name": "Momentum",
            "strategy_score": 80.0,
            "opportunity_score": 75.0,
            "risk_score": 20.0,
        },
    )()


def service():
    controlled = ControlledExecutionService(ExecutionEngine(adapter=FakeAdapter()), ReadyValidator())
    return ExecutionBridgeService(controlled)


def test_enqueue_opportunity_creates_ready_queue_item():
    bridge = service()
    accepted = bridge.enqueue_opportunity(account_id="acc-1", result=request_result())
    assert accepted.accepted is True
    assert accepted.result.status is ExecutionStatus.READY
    assert len(bridge.all()) == 1


def test_not_ready_opportunity_is_not_queued():
    bridge = service()
    accepted = bridge.enqueue_opportunity(account_id="acc-1", result=request_result(False))
    assert accepted.accepted is False
    assert accepted.result.status is ExecutionStatus.BLOCKED
    assert bridge.all() == ()


def test_request_confirmation_updates_queue_state():
    bridge = service()
    accepted = bridge.enqueue_opportunity(account_id="acc-1", result=request_result())
    result = bridge.request_confirmation(accepted.request.execution_id)
    assert result.status is ExecutionStatus.WAITING_CONFIRMATION
    assert bridge.get(accepted.request.execution_id).result.status is ExecutionStatus.WAITING_CONFIRMATION


def test_cancel_removes_terminal_queue_item():
    bridge = service()
    accepted = bridge.enqueue_opportunity(account_id="acc-1", result=request_result())
    bridge.request_confirmation(accepted.request.execution_id)
    result = bridge.cancel(accepted.request.execution_id)
    assert result.status is ExecutionStatus.CANCELLED
    assert bridge.remove_terminal(accepted.request.execution_id) is True
    assert bridge.all() == ()


def test_unknown_execution_id_is_rejected():
    bridge = service()
    with pytest.raises(KeyError):
        bridge.request_confirmation("missing")
