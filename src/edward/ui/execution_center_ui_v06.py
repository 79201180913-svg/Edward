from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.domain.execution import ExecutionEvent, ExecutionEventType, ExecutionStatus
from edward.services.execution_engine import ExecutionEngine, InMemoryExecutionJournal


STATUS_LABELS = {
    ExecutionStatus.CREATED: "Создано",
    ExecutionStatus.VALIDATING: "Проверка",
    ExecutionStatus.READY: "Готово к исполнению",
    ExecutionStatus.WAITING_CONFIRMATION: "Ожидает подтверждения",
    ExecutionStatus.SUBMITTING: "Отправка",
    ExecutionStatus.SUBMITTED: "Отправлено",
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

EVENT_LABELS = {
    ExecutionEventType.CREATED: "Исполнение создано",
    ExecutionEventType.VALIDATION_STARTED: "Начата проверка",
    ExecutionEventType.VALIDATION_PASSED: "Проверка пройдена",
    ExecutionEventType.VALIDATION_FAILED: "Проверка не пройдена",
    ExecutionEventType.REVALIDATION_STARTED: "Начата повторная проверка",
    ExecutionEventType.REVALIDATION_FAILED: "Повторная проверка не пройдена",
    ExecutionEventType.CONFIRMATION_REQUIRED: "Требуется подтверждение",
    ExecutionEventType.CONFIRMED: "Исполнение подтверждено",
    ExecutionEventType.SUBMITTING: "Отправка заявки",
    ExecutionEventType.SUBMITTED: "Заявка отправлена",
    ExecutionEventType.STATUS_CHANGED: "Изменён статус заявки",
    ExecutionEventType.FILL_UPDATED: "Обновлено исполнение",
    ExecutionEventType.CANCEL_REQUESTED: "Запрошена отмена",
    ExecutionEventType.CANCELLED: "Заявка отменена",
    ExecutionEventType.RECONCILIATION_STARTED: "Начата сверка",
    ExecutionEventType.RECONCILED: "Сверка завершена",
    ExecutionEventType.ERROR: "Ошибка исполнения",
}


def execution_status_label(status: ExecutionStatus | str) -> str:
    value = status if isinstance(status, ExecutionStatus) else ExecutionStatus(str(status))
    return STATUS_LABELS.get(value, value.value)


def execution_event_text(event: ExecutionEvent) -> str:
    label = EVENT_LABELS.get(event.event_type, event.event_type.value)
    return f"{label}: {event.message}"


def install_execution_center_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_execution_center_ui_v06_installed", False):
        return

    original_shell = app_class._shell

    def shell(self: Any) -> None:
        original_shell(self)
        if hasattr(self, "nav") and not getattr(self, "_execution_nav_added_v06", False):
            ttk.Button(
                self.nav,
                text="Исполнение",
                style="Nav.TButton",
                command=self.open_execution_center,
            ).pack(fill="x", pady=2)
            self._execution_nav_added_v06 = True

    def open_execution_center(self: Any) -> None:
        existing = getattr(self, "_execution_center_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    return
            except tk.TclError:
                pass

        window = tk.Toplevel(self)
        window.title("Edward — Центр исполнения")
        window.geometry("1180x760")
        window.minsize(980, 640)
        self._execution_center_window = window

        status_var = tk.StringVar(value="Готов")
        mode_var = tk.StringVar(value="Ожидание")
        account_var = tk.StringVar(value=str(getattr(getattr(self, "context", None), "active_account_id", "") or "—"))
        active_status_var = tk.StringVar(value="Нет активной операции")
        readiness_var = tk.StringVar(value="—")
        operation_var = tk.StringVar(value="Выберите операцию в очереди")

        header = ttk.Frame(window, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text="Центр исполнения", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Статус сервиса:").pack(side="left", padx=(24, 4))
        ttk.Label(header, textvariable=status_var).pack(side="left")
        ttk.Label(header, text="Счёт:").pack(side="left", padx=(24, 4))
        ttk.Label(header, textvariable=account_var).pack(side="left")
        ttk.Label(header, text="Режим:").pack(side="left", padx=(24, 4))
        ttk.Label(header, textvariable=mode_var).pack(side="left")

        toolbar = ttk.Frame(window, padding=(16, 0, 16, 10))
        toolbar.pack(fill="x")
        start_button = ttk.Button(toolbar, text="Запустить")
        start_button.pack(side="left")
        stop_button = ttk.Button(toolbar, text="Остановить")
        stop_button.pack(side="left", padx=6)
        emergency_button = ttk.Button(toolbar, text="Аварийная остановка")
        emergency_button.pack(side="left")

        body = ttk.Frame(window, padding=(16, 0, 16, 16))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)
        body.rowconfigure(2, weight=1)

        queue_frame = ttk.LabelFrame(body, text="Очередь исполнения", padding=8)
        queue_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8), pady=(0, 8))
        queue_frame.rowconfigure(0, weight=1)
        queue_tree = ttk.Treeview(
            queue_frame,
            columns=("instrument", "decision", "quantity", "readiness", "status"),
            show="headings",
            height=14,
        )
        for key, title, width in (
            ("instrument", "Инструмент", 120),
            ("decision", "Решение", 100),
            ("quantity", "Количество", 110),
            ("readiness", "Готовность", 140),
            ("status", "Статус", 170),
        ):
            queue_tree.heading(key, text=title)
            queue_tree.column(key, width=width, anchor="center")
        queue_tree.grid(row=0, column=0, sticky="nsew")

        current_frame = ttk.LabelFrame(body, text="Текущая операция", padding=10)
        current_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
        ttk.Label(current_frame, textvariable=operation_var, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(current_frame, text="Execution Readiness:").pack(anchor="w")
        ttk.Label(current_frame, textvariable=readiness_var).pack(anchor="w", pady=(2, 8))
        ttk.Label(current_frame, textvariable=active_status_var).pack(anchor="w")

        progress_frame = ttk.LabelFrame(body, text="Процесс", padding=10)
        progress_frame.grid(row=1, column=1, sticky="nsew", pady=(0, 8))
        progress_text = tk.Text(progress_frame, height=12, width=50, state="disabled", wrap="word")
        progress_text.pack(fill="both", expand=True)

        journal_frame = ttk.LabelFrame(body, text="Журнал", padding=8)
        journal_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        journal_text = tk.Text(journal_frame, height=8, state="disabled", wrap="word")
        journal_text.pack(fill="both", expand=True)

        journal = InMemoryExecutionJournal()

        def append_text(widget: tk.Text, text: str) -> None:
            try:
                widget.configure(state="normal")
                widget.insert("end", text + "\n")
                widget.see("end")
                widget.configure(state="disabled")
            except tk.TclError:
                pass

        def on_event(event: ExecutionEvent) -> None:
            text = execution_event_text(event)
            if window.winfo_exists():
                window.after(0, lambda: append_text(journal_text, text))
                window.after(0, lambda: append_text(progress_text, f"[{event.status.value}] {text}"))
                window.after(0, lambda: active_status_var.set(execution_status_label(event.status)))

        engine = ExecutionEngine(journal=journal, event_callback=on_event)
        self._execution_center_engine = engine

        def start_service() -> None:
            status_var.set("Готов")
            mode_var.set("Только подготовка")
            append_text(journal_text, "Execution Engine готов. Автоматическая отправка отключена.")

        def stop_service() -> None:
            status_var.set("Остановлен")
            mode_var.set("Ожидание")
            append_text(journal_text, "Execution Engine остановлен.")

        def emergency_stop() -> None:
            status_var.set("АВАРИЙНАЯ ОСТАНОВКА")
            mode_var.set("Остановлено")
            append_text(journal_text, "Аварийная остановка: новые операции заблокированы.")

        def close_window() -> None:
            try:
                window.destroy()
            finally:
                self._execution_center_window = None

        start_button.configure(command=start_service)
        stop_button.configure(command=stop_service)
        emergency_button.configure(command=emergency_stop)
        queue_tree.bind("<<TreeviewSelect>>", lambda _event: None)
        window.protocol("WM_DELETE_WINDOW", close_window)

        append_text(journal_text, "Центр исполнения открыт.")
        append_text(progress_text, "Ожидание ExecutionRequest.")

    app_class._shell = shell
    app_class.open_execution_center = open_execution_center
    app_class._execution_center_ui_v06_installed = True
