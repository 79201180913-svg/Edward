from types import SimpleNamespace

from edward.domain.execution import ExecutionEvent, ExecutionEventType, ExecutionStatus
from edward.ui.execution_center_ui_v06 import execution_event_text, execution_status_label


def test_execution_status_label_is_localized():
    assert execution_status_label(ExecutionStatus.READY) == "Готово к исполнению"
    assert execution_status_label(ExecutionStatus.PARTIALLY_FILLED) == "Частично исполнено"


def test_execution_event_text_is_localized():
    event = ExecutionEvent(
        execution_id="ex-1",
        event_type=ExecutionEventType.SUBMITTED,
        status=ExecutionStatus.SUBMITTED,
        message="Заявка отправлена",
    )
    assert execution_event_text(event) == "Заявка отправлена: Заявка отправлена"
