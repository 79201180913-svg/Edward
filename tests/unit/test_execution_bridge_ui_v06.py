from types import SimpleNamespace

from edward.domain.execution import ExecutionDecision, ExecutionRequest, ExecutionResult, ExecutionStatus
from edward.ui.execution_bridge_ui_v06 import can_enqueue_execution, enqueue_button_label


def request(*, ready=True):
    return ExecutionRequest(
        execution_id="ex-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=10,
        order_type="LIMIT",
        entry_price=100,
        execution_ready=ready,
    )


def test_enqueue_available_only_for_execution_ready_request():
    assert can_enqueue_execution(request(ready=True), ExecutionStatus.READY) is True
    assert can_enqueue_execution(request(ready=False), ExecutionStatus.BLOCKED) is False


def test_enqueue_button_label_is_localized():
    assert enqueue_button_label(True) == "Передать в исполнение"
    assert enqueue_button_label(False) == "Исполнение недоступно"
