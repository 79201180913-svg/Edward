from types import SimpleNamespace

from edward.domain.execution import ExecutionEvent, ExecutionEventType, ExecutionStatus
from edward.ui.execution_center_ui_v06 import execution_event_text, execution_status_label


def test_execution_status_label_is_localized():
    assert execution_status_label(ExecutionStatus.READY) == "Готово к подтверждению"
    assert execution_status_label(ExecutionStatus.PARTIALLY_FILLED) == "Частично исполнено"
    assert execution_status_label(ExecutionStatus.SUBMITTED) == "Заявка отправлена"


def test_execution_event_text_is_localized():
    event = ExecutionEvent(
        execution_id="ex-1",
        event_type=ExecutionEventType.SUBMITTED,
        status=ExecutionStatus.SUBMITTED,
        message="Заявка отправлена",
    )
    assert execution_event_text(event) == "Заявка отправлена: Заявка отправлена"


def test_confirmation_ui_statuses_hide_technical_pipeline():
    assert execution_status_label(ExecutionStatus.READY) != "PASS"
    assert execution_status_label(ExecutionStatus.BLOCKED) == "Исполнение заблокировано"
    assert execution_status_label(ExecutionStatus.WAITING_CONFIRMATION) == "Ожидает подтверждения"
