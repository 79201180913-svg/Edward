from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Type

from edward.domain.execution import ExecutionEvent, ExecutionEventType, ExecutionStatus

_STATUS_LABELS = {ExecutionStatus.CREATED: "Создано", ExecutionStatus.VALIDATING: "Проверка", ExecutionStatus.READY: "Готово к исполнению", ExecutionStatus.WAITING_CONFIRMATION: "Ожидает подтверждения", ExecutionStatus.SUBMITTING: "Отправка заявки", ExecutionStatus.SUBMITTED: "Заявка отправлена", ExecutionStatus.PARTIALLY_FILLED: "Частично исполнено", ExecutionStatus.FILLED: "Исполнено", ExecutionStatus.RECONCILED: "Сверено", ExecutionStatus.BLOCKED: "Заблокировано", ExecutionStatus.REJECTED: "Отклонено", ExecutionStatus.CANCELLED: "Отменено", ExecutionStatus.TIMEOUT: "Тайм-аут", ExecutionStatus.FAILED: "Ошибка", ExecutionStatus.RECONCILIATION_ERROR: "Ошибка сверки"}
_EVENT_LABELS = {ExecutionEventType.CREATED: "Исполнение создано", ExecutionEventType.VALIDATION_STARTED: "Начата проверка исполнения", ExecutionEventType.VALIDATION_PASSED: "Проверка исполнения пройдена", ExecutionEventType.VALIDATION_FAILED: "Исполнение заблокировано", ExecutionEventType.REVALIDATION_STARTED: "Начата повторная проверка", ExecutionEventType.REVALIDATION_FAILED: "Повторная проверка не пройдена", ExecutionEventType.CONFIRMATION_REQUIRED: "Требуется подтверждение пользователя", ExecutionEventType.CONFIRMED: "Пользователь подтвердил исполнение", ExecutionEventType.SUBMITTING: "Отправка заявки", ExecutionEventType.SUBMITTED: "Заявка отправлена", ExecutionEventType.STATUS_CHANGED: "Получен новый статус заявки", ExecutionEventType.FILL_UPDATED: "Обновлено исполнение", ExecutionEventType.CANCEL_REQUESTED: "Запрошена отмена заявки", ExecutionEventType.CANCELLED: "Заявка отменена", ExecutionEventType.RECONCILIATION_STARTED: "Начата сверка позиции", ExecutionEventType.RECONCILED: "Сверка завершена", ExecutionEventType.ERROR: "Ошибка исполнения"}

def execution_status_label(status: Any) -> str:
    try:
        key = status if isinstance(status, ExecutionStatus) else ExecutionStatus(str(getattr(status, "value", status)))
    except (ValueError, TypeError):
        return str(getattr(status, "value", status))
    return _STATUS_LABELS.get(key, key.value)

def execution_event_text(event: Any) -> str:
    if isinstance(event, ExecutionEvent):
        return f"{_EVENT_LABELS.get(event.event_type, event.event_type.value)}: {event.message}"
    if isinstance(event, ExecutionEventType):
        return _EVENT_LABELS.get(event, event.value)
    event_type = getattr(event, "event_type", None); message = getattr(event, "message", None)
    if event_type is not None:
        try:
            key = event_type if isinstance(event_type, ExecutionEventType) else ExecutionEventType(str(getattr(event_type, "value", event_type)))
            label = _EVENT_LABELS.get(key, key.value)
        except (ValueError, TypeError):
            label = str(getattr(event_type, "value", event_type))
        return f"{label}: {message}" if message else label
    return str(getattr(event, "value", event))

def build_execution_center_snapshot(*, account_label: str, service_status: str, mode_label: str, queue: list[dict[str, Any]], active: dict[str, Any] | None, events: list[Any]) -> dict[str, Any]:
    return {"account_label": account_label, "service_status": service_status, "mode_label": mode_label, "queue": queue, "active_status": execution_status_label(active.get("status")) if active else "Нет активной операции", "events": [{"time": getattr(e, "created_at", None), "text": execution_event_text(e), "status": execution_status_label(getattr(e, "status", "")), "message": getattr(e, "message", "")} for e in events]}

def _open_execution_center(self: Any) -> None:
    window = getattr(self, "_execution_center_window", None)
    if window is not None:
        try:
            if window.winfo_exists(): window.deiconify(); window.lift(); return
        except tk.TclError: pass
    window = tk.Toplevel(self); self._execution_center_window = window; window.title("Центр исполнения"); window.geometry("1050x700")
    root = ttk.Frame(window, padding=16); root.pack(fill="both", expand=True)
    ttk.Label(root, text="Центр исполнения", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(root, text="Режим: Требуется подтверждение").pack(anchor="w", pady=8)
    queue = ttk.LabelFrame(root, text="Очередь исполнения", padding=8); queue.pack(fill="x", pady=5)
    tree = ttk.Treeview(queue, columns=("ticker", "decision", "quantity", "price", "ready", "status"), show="headings", height=5); tree.pack(fill="x")
    for col, title in (("ticker", "Инструмент"), ("decision", "Решение"), ("quantity", "Количество"), ("price", "Цена"), ("ready", "Готовность"), ("status", "Статус")): tree.heading(col, text=title)
    active = ttk.LabelFrame(root, text="Текущая операция", padding=8); active.pack(fill="x", pady=5)
    ttk.Label(active, text="Нет активной операции", font=("Segoe UI", 12, "bold")).pack(anchor="w")
    steps = ttk.Treeview(active, columns=("step", "state"), show="headings", height=8); steps.pack(fill="x", pady=6); steps.heading("step", text="Этап"); steps.heading("state", text="Состояние")
    for label in ("Решение получено", "Execution Readiness", "Trading Status", "Проверка позиции", "Проверка денежных средств", "Pre-trade revalidation", "Подтверждение пользователя", "Отправка заявки", "Мониторинг", "Сверка"): steps.insert("", "end", values=(label, "Ожидание"))
    journal = ttk.LabelFrame(root, text="Журнал событий", padding=8); journal.pack(fill="both", expand=True, pady=5); text = tk.Text(journal, state="disabled", wrap="word"); text.pack(fill="both", expand=True)
    def close(): self._execution_center_window = None; window.destroy()
    window.protocol("WM_DELETE_WINDOW", close)

def install_execution_center_ui(app_cls: Type[Any]) -> None:
    if getattr(app_cls, "_execution_center_ui_v06_installed", False): return
    original_shell = app_cls._shell
    def wrapped_shell(self: Any, *args: Any, **kwargs: Any) -> None:
        original_shell(self, *args, **kwargs)
        button = ttk.Button(self.nav, text="Исполнение", style="Nav.TButton", command=self._open_execution_center); button.pack(fill="x", pady=2); self._execution_center_button = button
    app_cls._open_execution_center = _open_execution_center; app_cls._shell = wrapped_shell; app_cls._execution_center_ui_v06_installed = True

__all__ = ["execution_status_label", "execution_event_text", "build_execution_center_snapshot", "install_execution_center_ui"]
