from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
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
            if window.winfo_exists():
                window.deiconify(); window.lift(); return
        except tk.TclError:
            pass
    window = tk.Toplevel(self); self._execution_center_window = window; window.title("Центр исполнения"); window.geometry("1050x720")
    root = ttk.Frame(window, padding=16); root.pack(fill="both", expand=True)
    ttk.Label(root, text="Центр исполнения", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    header = ttk.Frame(root); header.pack(fill="x", pady=8)
    mode_var = tk.StringVar(value="Требуется подтверждение")
    status_var = tk.StringVar(value="Сервис: не подключён")
    active_var = tk.StringVar(value="Нет активной операции")
    ttk.Label(header, textvariable=status_var).pack(side="left"); ttk.Label(header, text="Режим:").pack(side="left", padx=(25, 5)); ttk.Label(header, textvariable=mode_var).pack(side="left")

    queue = ttk.LabelFrame(root, text="Очередь исполнения", padding=8); queue.pack(fill="x", pady=5)
    tree = ttk.Treeview(queue, columns=("ticker", "decision", "quantity", "price", "ready", "status"), show="headings", height=5); tree.pack(fill="x")
    for col, title in (("ticker", "Инструмент"), ("decision", "Решение"), ("quantity", "Количество"), ("price", "Цена"), ("ready", "Готовность"), ("status", "Статус")): tree.heading(col, text=title)

    active = ttk.LabelFrame(root, text="Текущая операция", padding=8); active.pack(fill="x", pady=5)
    ttk.Label(active, textvariable=active_var, font=("Segoe UI", 12, "bold")).pack(anchor="w")
    actions = ttk.Frame(active); actions.pack(fill="x", pady=(8, 2))
    prepare_button = ttk.Button(actions, text="Подготовить")
    confirm_request_button = ttk.Button(actions, text="Запросить подтверждение")
    confirm_submit_button = ttk.Button(actions, text="Подтвердить и отправить")
    cancel_button = ttk.Button(actions, text="Отменить")
    for button in (prepare_button, confirm_request_button, confirm_submit_button, cancel_button): button.pack(side="left", padx=(0, 8))

    steps = ttk.Treeview(active, columns=("step", "state"), show="headings", height=8); steps.pack(fill="x", pady=6); steps.heading("step", text="Этап"); steps.heading("state", text="Состояние")
    step_labels = ("Решение получено", "Execution Readiness", "Trading Status", "Проверка позиции", "Проверка денежных средств", "Pre-trade revalidation", "Подтверждение пользователя", "Отправка заявки", "Мониторинг", "Сверка")
    for label in step_labels: steps.insert("", "end", values=(label, "Ожидание"))

    journal = ttk.LabelFrame(root, text="Журнал событий", padding=8); journal.pack(fill="both", expand=True, pady=5)
    text = tk.Text(journal, state="disabled", wrap="word"); text.pack(fill="both", expand=True)

    def current_controller():
        controller = getattr(self, "_execution_center_controller", None)
        if controller is None:
            messagebox.showwarning("Центр исполнения", "Сервис исполнения ещё не подключён.")
        return controller

    def redraw(state: Any) -> None:
        status_var.set(f"Сервис: {execution_status_label(state.status) if state.status else 'Готов'}")
        request = state.request
        active_var.set(f"{request.ticker} / {request.decision.value} / {request.quantity} шт." if request else "Нет активной операции")
        tree.delete(*tree.get_children())
        if request:
            tree.insert("", "end", values=(request.ticker, request.decision.value, str(request.quantity), str(request.entry_price or "—"), "ДА" if request.execution_ready else "НЕТ", execution_status_label(state.status or ExecutionStatus.CREATED)))
        for item in steps.get_children(): steps.delete(item)
        for label in step_labels:
            state_text = "Ожидание"
            if label == "Решение получено" and request: state_text = "Готово"
            if label == "Execution Readiness" and request: state_text = "PASS" if request.execution_ready else "FAIL"
            if label == "Pre-trade revalidation" and state.status is ExecutionStatus.BLOCKED: state_text = "FAIL"
            if label == "Подтверждение пользователя" and state.status is ExecutionStatus.WAITING_CONFIRMATION: state_text = "Ожидается"
            if label == "Отправка заявки" and state.status in {ExecutionStatus.SUBMITTING, ExecutionStatus.SUBMITTED}: state_text = execution_status_label(state.status)
            steps.insert("", "end", values=(label, state_text))
        text.configure(state="normal"); text.delete("1.0", "end")
        for event in state.events: text.insert("end", execution_event_text(event) + "\n")
        text.configure(state="disabled")
        prepare_button.configure(state="normal" if request and state.status is ExecutionStatus.CREATED else "disabled")
        confirm_request_button.configure(state="normal" if state.status is ExecutionStatus.READY else "disabled")
        confirm_submit_button.configure(state="normal" if state.status is ExecutionStatus.WAITING_CONFIRMATION else "disabled")
        cancel_button.configure(state="normal" if state.status is ExecutionStatus.WAITING_CONFIRMATION else "disabled")

    def invoke(action):
        controller = current_controller()
        if controller is None: return
        try: action(controller)
        except Exception as exc: messagebox.showerror("Центр исполнения", str(exc))
        redraw(controller.state)

    prepare_button.configure(command=lambda: invoke(lambda c: c.prepare()))
    confirm_request_button.configure(command=lambda: invoke(lambda c: c.request_confirmation()))
    confirm_submit_button.configure(command=lambda: invoke(lambda c: c.confirm_and_submit()))
    cancel_button.configure(command=lambda: invoke(lambda c: c.cancel()))

    controller = getattr(self, "_execution_center_controller", None)
    if controller is not None:
        controller.on_change = redraw
        redraw(controller.state)

    def close(): self._execution_center_window = None; window.destroy()
    window.protocol("WM_DELETE_WINDOW", close)


def install_execution_center_ui(app_cls: Type[Any]) -> None:
    if getattr(app_cls, "_execution_center_ui_v06_installed", False): return
    original_shell = app_cls._shell
    def bind_execution_controller(self: Any, controller: Any) -> None:
        self._execution_center_controller = controller
        if getattr(self, "_execution_center_window", None) is not None:
            try:
                controller.on_change = lambda state: None
            except Exception:
                pass
    def wrapped_shell(self: Any, *args: Any, **kwargs: Any) -> None:
        original_shell(self, *args, **kwargs)
        button = ttk.Button(self.nav, text="Исполнение", style="Nav.TButton", command=self._open_execution_center); button.pack(fill="x", pady=2); self._execution_center_button = button
    app_cls.bind_execution_controller = bind_execution_controller
    app_cls._open_execution_center = _open_execution_center; app_cls._shell = wrapped_shell; app_cls._execution_center_ui_v06_installed = True


__all__ = ["execution_status_label", "execution_event_text", "build_execution_center_snapshot", "install_execution_center_ui"]
