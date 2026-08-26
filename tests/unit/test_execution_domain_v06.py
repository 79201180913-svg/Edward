from datetime import datetime, timezone
from decimal import Decimal

import pytest

from edward.domain import (
    ExecutionDecision,
    ExecutionEvent,
    ExecutionEventType,
    ExecutionJournalEntry,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)


def request(**overrides):
    values = {
        "execution_id": "exec-1",
        "account_id": "acc-1",
        "instrument_uid": "uid-1",
        "ticker": "TEST",
        "decision": ExecutionDecision.BUY,
        "side": "BUY",
        "quantity": Decimal("100"),
        "order_type": "LIMIT",
        "entry_price": Decimal("10.25"),
        "stop_price": Decimal("9.50"),
        "execution_ready": True,
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return ExecutionRequest(**values)


def test_execution_request_is_immutable_and_validates_required_fields():
    item = request()
    assert item.execution_id == "exec-1"
    with pytest.raises((AttributeError, TypeError)):
        item.quantity = Decimal("50")

    with pytest.raises(ValueError, match="quantity must be positive"):
        request(quantity=Decimal("0"))

    with pytest.raises(ValueError, match="execution_id is required"):
        request(execution_id="")


def test_execution_request_rejects_non_executable_decision():
    with pytest.raises(ValueError, match="decision is not executable"):
        request(decision="WAIT")


def test_execution_result_tracks_broker_lifecycle_values():
    result = ExecutionResult(
        execution_id="exec-1",
        status=ExecutionStatus.PARTIALLY_FILLED,
        broker_order_id="order-1",
        filled_quantity=Decimal("40"),
        average_fill_price=Decimal("10.30"),
        commission=Decimal("1.25"),
    )
    assert result.status is ExecutionStatus.PARTIALLY_FILLED
    assert result.filled_quantity == Decimal("40")
    assert result.broker_order_id == "order-1"


def test_execution_event_carries_status_and_payload():
    event = ExecutionEvent(
        execution_id="exec-1",
        event_type=ExecutionEventType.VALIDATION_PASSED,
        status=ExecutionStatus.READY,
        message="Pre-trade validation passed",
        payload={"trading_status": "NORMAL"},
    )
    assert event.event_type is ExecutionEventType.VALIDATION_PASSED
    assert event.status is ExecutionStatus.READY
    assert event.payload["trading_status"] == "NORMAL"


def test_execution_journal_entry_keeps_persistent_execution_identity():
    entry = ExecutionJournalEntry(
        execution_id="exec-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        decision=ExecutionDecision.SELL,
        side="SELL",
        order_type="MARKET",
        requested_quantity=Decimal("75"),
        requested_price=None,
        stop_price=None,
        execution_ready=True,
        broker_order_id="order-1",
        filled_quantity=Decimal("75"),
        status=ExecutionStatus.RECONCILED,
    )
    assert entry.execution_id == "exec-1"
    assert entry.broker_order_id == "order-1"
    assert entry.status is ExecutionStatus.RECONCILED
