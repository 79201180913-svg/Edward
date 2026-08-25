from __future__ import annotations

from typing import Any

from edward.domain.execution import ExecutionEventType, ExecutionStatus


_STATUS_LABELS = {
    ExecutionStatus.CREATED: "Создано",
    ExecutionStatus.VALIDATING: "Проверка",
    ExecutionStatus.READY: "Готово",
    ExecutionStatus.WAITING_CONFIRMATION: "Ожидает подтверждения",
    ExecutionStatus.SUBMITTING: "Отправка заявки",
    ExecutionStatus.SUBMITTED: "Заявка отправлена",
    ExecutionStatus.PARTIALLY_FILLED: "Частично исполнено",
    ExecutionStatus.FILLED: "Исполнено",
    ExecutionStatus.RECONCILED: "Сверено",
    ExecutionStatus.BLOCKED: "Заблокировано",
    ExecutionStatus.REJECTED: "Отклонено",
    ExecutionStatus.CANCELLED: "Отменено",
    ExecutionStatus.TIMEOUT: "Тайм-аут",
    ExecutionStatus.FAILED: "Ошибка",
    ExecutionStatus.RECONCILIATION_ERROR: "Ошибка сверки",
}

_EVENT_LABELS = {
    ExecutionEventType.CREATED: "Исполнение создано",
    ExecutionEventType.VALIDATION_STARTED: "Начата проверка исполнения",
    ExecutionEventType.VALIDATION_PASSED: "Проверка исполнения пройдена",
    ExecutionEventType.VALIDATION_FAILED: "Исполнение заблокировано",
    ExecutionEventType.REVALIDATION_STARTED: "Начата повторная проверка",
    ExecutionEventType.REVALIDATION_FAILED: "Повторная проверка не пройдена",
    ExecutionEventType.CONFIRMATION_REQUIRED: "Требуется подтверждение пользователя",
    ExecutionEventType.CONFIRMED: "Пользователь подтвердил исполнение",
    ExecutionEventType.SUBMITTING: "Отправка заявки",
    ExecutionEventType.SUBMITTED: "Заявка отправлена",
    ExecutionEventType.STATUS_CHANGED: "Получен новый статус заявки",
    ExecutionEventType.FILL_UPDATED: "Обновлено исполнение",
    ExecutionEventType.CANCEL_REQUESTED: "Запрошена отмена заявки",
    ExecutionEventType.CANCELLED: "Заявка отменена",
    ExecutionEventType.RECONCILIATION_STARTED: "Начата сверка позиции",
    ExecutionEventType.RECONCILED: "Сверка завершена",
    ExecutionEventType.ERROR: "Ошибка исполнения",
}


def execution_status_label(status: Any) -> str:
    try:
        key = status if isinstance(status, ExecutionStatus) else ExecutionStatus(str(getattr(status, "value", status)))
    except (ValueError, TypeError):
        return str(getattr(status, "value", status))
    return _STATUS_LABELS.get(key, key.value)


def execution_event_text(event_type: Any) -> str:
    try:
        key = event_type if isinstance(event_type, ExecutionEventType) else ExecutionEventType(str(getattr(event_type, "value", event_type)))
    except (ValueError, TypeError):
        return str(getattr(event_type, "value", event_type))
    return _EVENT_LABELS.get(key, key.value)


def build_execution_center_snapshot(
    *,
    account_label: str,
    service_status: str,
    mode_label: str,
    queue: list[dict[str, Any]],
    active: dict[str, Any] | None,
    events: list[Any],
) -> dict[str, Any]:
    """Build a UI-neutral snapshot for the Execution Center and its tests."""
    active_status = execution_status_label(active.get("status")) if active else "Нет активной операции"
    return {
        "account_label": account_label,
        "service_status": service_status,
        "mode_label": mode_label,
        "queue": queue,
        "active_status": active_status,
        "events": [
            {
                "time": getattr(event, "created_at", None),
                "text": execution_event_text(getattr(event, "event_type", event)),
                "status": execution_status_label(getattr(event, "status", "")),
                "message": getattr(event, "message", ""),
            }
            for event in events
        ],
    }


__all__ = ["execution_status_label", "execution_event_text", "build_execution_center_snapshot"]
