from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Type

from edward.domain.execution import ExecutionEvent, ExecutionEventType, ExecutionStatus

_STATUS_LABELS = {
    ExecutionStatus.CREATED: "Готово к передаче",
    ExecutionStatus.VALIDATING: "Проверка",
    ExecutionStatus.READY: "Готово к подтверждению",
    ExecutionStatus.WAITING_CONFIRMATION: "Ожидает подтверждения",
    ExecutionStatus.SUBMITTING: "Отправка заявки",
    ExecutionStatus.SUBMITTED: "Заявка отправлена",
    ExecutionStatus.PARTIALLY_FILLED: "Частично исполнено",
    ExecutionStatus.FILLED: "Исполнено",
    ExecutionStatus.RECONCILED: "Сверено",
    ExecutionStatus.BLOCKED: "Исполнение заблокировано",
    ExecutionStatus.REJECTED: "Отклонено",
    ExecutionStatus.CANCELLED: "Отменено",
    ExecutionStatus.TIMEOUT: "Тайм-аут",
    ExecutionStatus.FAILED: "Ошибка исполнения",
    ExecutionStatus.RECONCILIATION_ERROR: "Ошибка сверки",
}

_EVENT_LABELS = {
    ExecutionEventType.CREATED: "Исполнение создано",
    ExecutionEventType.VALIDATION_STARTED: "Начата проверка исполнения",
    ExecutionEventType.VALIDATION_PASSED: "Проверка исполнения пройдена",
    ExecutionEventType.VALIDATION_FAILED: "Исполнение заблокировано",
    ExecutionEventType.REVALIDATION_STARTED: "Повторная проверка",
    ExecutionEventType.REVALIDATION_FAILED: "Повторная проверка не пройдена",
    ExecutionEventType.CONFIRMATION_REQUIRED: "Ожидается подтверждение",
    ExecutionEventType.CONFIRMED: "Исполнение подтверждено",
    ExecutionEventType.SUBMITTING: "Отправка заявки",
    ExecutionEventType.SUBMITTED: "Заявка отправлена",
    ExecutionEventType.STATUS_CHANGED: "Изменён статус заявки",
    ExecutionEventType.FILL_UPDATED: "Обновлено исполнение",
    ExecutionEventType.CANCEL_REQUESTED: "Запрошена отмена заявки",
    ExecutionEventType.CANCELLED: "Заявка отменена",
    ExecutionEventType.RECONCILIATION_STARTED: "Начата сверка",
    ExecutionEventType.RECONCILED: "Сверка завершена",
    ExecutionEventType.ERROR: "Ошибка исполнения",
}


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
    event_type = getattr(event, "event_type", None)
    message = getattr(event, "message", None)
    if event_type is not None:
        try:
            key = event_type if isinstance(event_type, ExecutionEventType) else ExecutionEventType(str(getattr(event_type, "value", event_type)))
            label = _EVENT_LABELS.get(key, key.value)
        except (ValueError, TypeError):
            label = str(getattr(event_type, "value", event_type))
        return f"{label}: {message}" if message else label
    return str(getattr(event, "value", event))


def build_execution_center_snapshot(*, account_label: str, service_status: str, mode_label: str, queue: list[dict[str, Any]], active: dict[str, Any] | None, events: list[Any]) -> dict[str, Any]:
    return {
        "account_label": account_label,
        "service_status": service_status,
        "mode_label": mode_label,
        "queue": queue,
        "active_status": execution_status_label(active.get("status")) if active else "Нет активной операции",
        "events": [
            {
                "time": getattr(e, "created_at", None),
                "text": execution_event_text(e),
                "status": execution_status_label(getattr(e, "status", "")),
                "message": getattr(e, "message", ""),
            }
            for e in events
        ],
    }


def _open_execution_center(self: Any) -> None:
    window = getattr(self, "_execution_center_window", None)
    if window is not None:
        try:
            if window.winfo_exists():
                window.deiconify()
                window.lift()
                return
        except tk.TclError:
            pass

    window = tk.Toplevel(self)
    self._execution_center_window = window
    window.title("Центр исполнения")
    window.geometry("1050x650")

    root = ttk.Frame(window, padding=16)
    root.pack(fill="both", expand=True)
    ttk.Label(root, text="Центр исполнения", font=("Segoe UI", 18, "bold")).pack(anchor="w")

    header = ttk.Frame(root)
    header.pack(fill="x", pady=8)
    status_var = tk.StringVar(value="Сервис готов")
    mode_var = tk.StringVar(value="Подтверждение пользователя")
    ttk.Label(header, textvariable=status_var).pack(side="left")
    ttk.Label(header, text="Режим:").pack(side="left", padx=(25, 5))
    ttk.Label(header, textvariable=mode_var).pack(side="left")

    queue = ttk.LabelFrame(root, text="Очередь исполнения", padding=8)
    queue.pack(fill="x", pady=5)
    tree = ttk.Treeview(
        queue,
        columns=("ticker", "decision", "quantity", "price", "ready", "status"),
        show="headings",
        height=5,
    )
    tree.pack(fill="x")
    for col, title in (
        ("ticker", "Инструмент"),
        ("decision", "Решение"),
        ("quantity", "Количество"),
        ("price", "Цена"),
        ("ready", "Готовность"),
        ("status", "Статус"),
    ):
        tree.heading(col, text=title)

    active = ttk.LabelFrame(root, text="Операция", padding=12)
    active.pack(fill="x", pady=6)
    summary_var = tk.StringVar(value="Нет активной операции")
    ttk.Label(active, textvariable=summary_var, font=("Segoe UI", 13, "bold")).pack(anchor="w")

    confirmation_var = tk.StringVar(value="")
    confirmation_label = ttk.Label(active, textvariable=confirmation_var, wraplength=900, justify="left")
    confirmation_label.pack(anchor="w", pady=(6, 4))

    detail_var = tk.StringVar(value="")
    ttk.Label(active, textvariable=detail_var, wraplength=900, justify="left").pack(anchor="w")

    actions = ttk.Frame(active)
    actions.pack(fill="x", pady=(12, 2))
    prepare_button = ttk.Button(actions, text="Передать в исполнение")
    confirm_request_button = ttk.Button(actions, text="Подтвердить")
    confirm_submit_button = ttk.Button(actions, text="Подтвердить и отправить")
    cancel_button = ttk.Button(actions, text="Отменить")
    for button in (prepare_button, confirm_request_button, confirm_submit_button, cancel_button):
        button.pack(side="left", padx=(0, 8))

    journal = ttk.LabelFrame(root, text="Журнал событий", padding=8)
    journal.pack(fill="both", expand=True, pady=6)
    text = tk.Text(journal, state="disabled", wrap="word", height=8)
    text.pack(fill="both", expand=True)

    def current_controller():
        controller = getattr(self, "_execution_center_controller", None)
        if controller is None:
            messagebox.showwarning("Центр исполнения", "Сервис исполнения ещё не подключён.")
        return controller

    def bridge_items() -> tuple[Any, ...]:
        bridge = getattr(self, "_execution_bridge", None)
        if bridge is None:
            return ()
        try:
            return bridge.all()
        except Exception:
            return ()

    def redraw(state: Any) -> None:
        request = state.request
        busy = bool(state.busy)

        if state.error:
            status_var.set(f"Ошибка: {state.error}")
        elif busy:
            status_var.set("Сервис: выполняется…")
        elif state.status is ExecutionStatus.SUBMITTED:
            status_var.set("Заявка отправлена")
        elif state.status is ExecutionStatus.BLOCKED:
            status_var.set("Исполнение заблокировано")
        elif state.status is ExecutionStatus.WAITING_CONFIRMATION:
            status_var.set("Ожидает подтверждения")
        elif request is not None and state.status in {ExecutionStatus.CREATED, ExecutionStatus.READY}:
            status_var.set("Готово к исполнению")
        else:
            status_var.set("Сервис готов")

        if request is None:
            summary_var.set("Нет активной операции")
            confirmation_var.set("")
            detail_var.set("")
        else:
            price_text = str(request.entry_price) if request.entry_price is not None else "по рыночной цене"
            summary_var.set(f"{request.ticker} · {request.decision.value} · {request.quantity} шт. · {price_text}")
            if state.status is ExecutionStatus.CREATED:
                confirmation_var.set("Решение готово. Передайте его в исполнение, чтобы подготовить заявку.")
                detail_var.set("После передачи система покажет краткое подтверждение перед отправкой.")
            elif state.status is ExecutionStatus.READY:
                confirmation_var.set("Заявка подготовлена. Проверьте условия и подтвердите передачу.")
                detail_var.set("Перед отправкой система автоматически перепроверит доступность инструмента, позицию и актуальную цену.")
            elif state.status is ExecutionStatus.WAITING_CONFIRMATION:
                confirmation_var.set("Подтвердите отправку заявки.")
                detail_var.set("Перед отправкой система автоматически перепроверит доступность инструмента, позицию и актуальную цену.")
            elif state.status is ExecutionStatus.SUBMITTING:
                confirmation_var.set("Заявка отправляется…")
                detail_var.set("")
            elif state.status is ExecutionStatus.SUBMITTED:
                confirmation_var.set("Заявка отправлена брокеру.")
                detail_var.set(f"Брокерский ID: {state.result.broker_order_id}" if state.result and state.result.broker_order_id else "")
            elif state.status is ExecutionStatus.BLOCKED:
                confirmation_var.set("Отправка запрещена: повторная проверка не пройдена.")
                detail_var.set(state.result.error_message if state.result and state.result.error_message else state.error or "Причина не указана.")
            elif state.status is ExecutionStatus.FAILED:
                confirmation_var.set("Не удалось отправить заявку.")
                detail_var.set(state.error or state.result.error_message if state.result else state.error or "Причина не указана.")
            else:
                confirmation_var.set(execution_status_label(state.status))
                detail_var.set("")

        tree.delete(*tree.get_children())
        items = bridge_items()
        if not items and request is not None:
            tree.insert(
                "",
                "end",
                iid=request.execution_id,
                values=(
                    request.ticker,
                    request.decision.value,
                    str(request.quantity),
                    str(request.entry_price or "—"),
                    "ДА" if request.execution_ready else "НЕТ",
                    execution_status_label(state.status or ExecutionStatus.CREATED),
                ),
            )
        else:
            for item in items:
                req = item.request
                tree.insert(
                    "",
                    "end",
                    iid=req.execution_id,
                    values=(
                        req.ticker,
                        req.decision.value,
                        str(req.quantity),
                        str(req.entry_price or "—"),
                        "ДА" if req.execution_ready else "НЕТ",
                        execution_status_label(item.result.status),
                    ),
                )
        if request is not None and request.execution_id in tree.get_children(""):
            tree.selection_set(request.execution_id)
            tree.focus(request.execution_id)

        text.configure(state="normal")
        text.delete("1.0", "end")
        for event in state.events:
            text.insert("end", execution_event_text(event) + "\n")
        if state.error:
            text.insert("end", f"Ошибка: {state.error}\n")
        text.configure(state="disabled")

        prepare_button.configure(state="normal" if request and state.status is ExecutionStatus.CREATED and not busy else "disabled")
        confirm_request_button.configure(state="normal" if state.status is ExecutionStatus.READY and not busy else "disabled")
        confirm_submit_button.configure(state="normal" if state.status is ExecutionStatus.WAITING_CONFIRMATION and not busy else "disabled")
        cancel_button.configure(state="normal" if state.status is ExecutionStatus.WAITING_CONFIRMATION and not busy else "disabled")

    def select_queue_item(_event: Any = None) -> None:
        selection = tree.selection()
        if not selection:
            return
        execution_id = selection[0]
        bridge = getattr(self, "_execution_bridge", None)
        controller = current_controller()
        if bridge is None or controller is None:
            return
        current_request = getattr(controller.state, "request", None)
        if current_request is not None and current_request.execution_id == execution_id:
            return
        try:
            item = bridge.get(execution_id)
            if item is None:
                return
            controller.load_queue_item(item)
        except Exception as exc:
            messagebox.showerror("Центр исполнения", str(exc))
            return
        redraw(controller.state)

    def invoke(action):
        controller = current_controller()
        if controller is None:
            return
        try:
            action(controller)
        except Exception as exc:
            messagebox.showerror("Центр исполнения", str(exc))
            return
        redraw(controller.state)

    def invoke_async_submit() -> None:
        controller = current_controller()
        if controller is None:
            return
        try:
            controller.confirm_and_submit_async()
        except Exception as exc:
            messagebox.showerror("Центр исполнения", str(exc))
            redraw(controller.state)

    prepare_button.configure(command=lambda: invoke(lambda c: c.prepare()))
    confirm_request_button.configure(command=lambda: invoke(lambda c: c.request_confirmation()))
    confirm_submit_button.configure(command=invoke_async_submit)
    cancel_button.configure(command=lambda: invoke(lambda c: c.cancel()))
    tree.bind("<<TreeviewSelect>>", select_queue_item, add="+")

    controller = getattr(self, "_execution_center_controller", None)
    if controller is not None:
        controller.dispatch = lambda callback, state: self.after(0, callback, state)
        controller.on_change = redraw
        if controller.state.request is None:
            items = bridge_items()
            if items:
                controller.load_queue_item(items[-1])
        redraw(controller.state)

    def close():
        controller = getattr(self, "_execution_center_controller", None)
        if controller is not None:
            controller.close()
        self._execution_center_window = None
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)


def install_execution_center_ui(app_cls: Type[Any]) -> None:
    if getattr(app_cls, "_execution_center_ui_v06_installed", False):
        return
    original_shell = app_cls._shell

    def bind_execution_controller(self: Any, controller: Any) -> None:
        self._execution_center_controller = controller
        if hasattr(self, "after"):
            controller.dispatch = lambda callback, state: self.after(0, callback, state)
        if getattr(self, "_execution_center_window", None) is not None:
            try:
                controller.on_change = lambda state: None
            except Exception:
                pass

    def wrapped_shell(self: Any, *args: Any, **kwargs: Any) -> None:
        original_shell(self, *args, **kwargs)
        button = ttk.Button(self.nav, text="Исполнение", style="Nav.TButton", command=self._open_execution_center)
        button.pack(fill="x", pady=2)
        self._execution_center_button = button

    app_cls.bind_execution_controller = bind_execution_controller
    app_cls._open_execution_center = _open_execution_center
    app_cls._shell = wrapped_shell
    app_cls._execution_center_ui_v06_installed = True


__all__ = ["execution_status_label", "execution_event_text", "build_execution_center_snapshot", "install_execution_center_ui"]