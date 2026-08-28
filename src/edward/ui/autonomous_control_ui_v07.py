from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from edward.domain.execution import ExecutionMode
from edward.services.autonomous_run_state_service import AutonomousRunMode, AutonomousRunStateService


_GLOBAL_EXECUTION_EVENT_SINK: Callable[[dict[str, Any]], None] | None = None


def publish_execution_event(event: dict[str, Any]) -> None:
    sink = _GLOBAL_EXECUTION_EVENT_SINK
    if sink is None:
        return
    try:
        sink(event)
    except Exception:
        pass


class AutonomousControlPanel:
    """Explicit controls and compact execution lifecycle monitor for v0.7."""

    def __init__(self, parent: Any, *, state_service: AutonomousRunStateService | None = None, on_state: Callable[[Any], None] | None = None, on_start: Callable[[], None] | None = None, on_pause: Callable[[], None] | None = None, on_stop: Callable[[], None] | None = None) -> None:
        self.state = state_service or AutonomousRunStateService()
        self.on_state = on_state
        self.on_start = on_start
        self.on_pause = on_pause
        self.on_stop = on_stop
        self.start_command: Callable[[], None] | None = None
        self.pause_command: Callable[[], None] | None = None
        self.stop_command: Callable[[], None] | None = None
        self._status_callback: Callable[[str], None] | None = None
        self._execution_rows: dict[tuple[int, str], str] = {}
        self.frame = ttk.LabelFrame(parent, text="Режим автономной торговли", padding=10)
        self.mode_var = tk.StringVar(value="analysis")
        self.interval_var = tk.StringVar(value="5 мин")
        self.status_var = tk.StringVar(value="Готово")

        ttk.Radiobutton(self.frame, text="Только анализ", value="analysis", variable=self.mode_var, command=self._mode_changed).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(self.frame, text="Автономная торговля", value="autonomous", variable=self.mode_var, command=self._mode_changed).pack(side="left", padx=(0, 12))
        ttk.Label(self.frame, text="Интервал:").pack(side="left")
        self.interval_combo = ttk.Combobox(self.frame, textvariable=self.interval_var, state="readonly", values=("1 мин", "5 мин", "15 мин", "30 мин", "1 час"), width=8)
        self.interval_combo.pack(side="left", padx=(5, 12))
        self.interval_combo.bind("<<ComboboxSelected>>", self._interval_changed)
        self.start_button = ttk.Button(self.frame, text="▶ Запустить автономную торговлю", command=self._start_clicked)
        self.start_button.pack(side="left", padx=(0, 6))
        self.pause_button = ttk.Button(self.frame, text="⏸ Пауза", command=self._pause_clicked)
        self.pause_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(self.frame, text="■ Остановить", command=self._stop_clicked)
        self.stop_button.pack(side="left", padx=(0, 12))
        ttk.Label(self.frame, textvariable=self.status_var).pack(side="left")

        monitor = ttk.LabelFrame(parent, text="Исполнение автономных сделок", padding=6)
        monitor.pack(fill="x", pady=(0, 10))
        columns = ("№", "Действие", "Тикер", "Статус", "Execution ID", "Причина")
        self.execution_tree = ttk.Treeview(monitor, columns=columns, show="headings", height=5)
        widths = {"№": 45, "Действие": 80, "Тикер": 90, "Статус": 115, "Execution ID": 220, "Причина": 500}
        for column in columns:
            self.execution_tree.heading(column, text=column)
            self.execution_tree.column(column, width=widths[column], anchor="w")
        self.execution_tree.pack(fill="x")

        self.frame.after(250, self._poll_runtime_state)
        self._refresh_controls()

    @property
    def status_callback(self) -> Callable[[str], None] | None:
        return self._status_callback

    @status_callback.setter
    def status_callback(self, callback: Callable[[str], None] | None) -> None:
        global _GLOBAL_EXECUTION_EVENT_SINK
        self._status_callback = callback
        _GLOBAL_EXECUTION_EVENT_SINK = self._handle_execution_event

    def _handle_execution_event(self, event: dict[str, Any]) -> None:
        sequence = int(event.get("sequence", 0) or 0)
        ticker = str(event.get("ticker", "") or "")
        action = str(event.get("action", "") or "")
        status = str(event.get("status", "") or "")
        execution_id = str(event.get("execution_id", "") or "—")
        reason = str(event.get("reason", "") or "")
        key = (sequence, ticker)
        def apply() -> None:
            values = (sequence, action, ticker, status, execution_id, reason)
            item = self._execution_rows.get(key)
            if item and self.execution_tree.exists(item):
                self.execution_tree.item(item, values=values)
            else:
                item = self.execution_tree.insert("", "end", values=values)
                self._execution_rows[key] = item
            children = self.execution_tree.get_children()
            if len(children) > 5:
                for old in children[:-5]:
                    self.execution_tree.delete(old)
                    for old_key, old_item in tuple(self._execution_rows.items()):
                        if old_item == old:
                            self._execution_rows.pop(old_key, None)
            if self._status_callback is not None:
                self._status_callback(f"Исполнение: #{sequence} {action} {ticker} → {status}: {reason}")
        try:
            self.frame.after(0, apply)
        except Exception:
            pass

    def pack(self, **kwargs: Any) -> None:
        self.frame.pack(**kwargs)

    def grid(self, **kwargs: Any) -> None:
        self.frame.grid(**kwargs)

    def _mode_changed(self) -> None:
        mode = AutonomousRunMode.AUTONOMOUS if self.mode_var.get() == "autonomous" else AutonomousRunMode.ANALYSIS
        self.state.set_mode(mode)
        if mode is AutonomousRunMode.ANALYSIS and self.state.snapshot().enabled:
            self.state.set_enabled(False)
        self._refresh_controls()
        self._notify()

    def _interval_changed(self, _event: Any = None) -> None:
        print(f"[AUTONOMOUS][UI] interval selected: {self.interval_var.get()}", flush=True)
        self._notify()

    def _start_clicked(self) -> None:
        print(f"[AUTONOMOUS][UI] start button pressed; interval={self.interval_minutes()}m", flush=True)
        self.state.set_enabled(True)
        self._refresh_controls()
        self._notify()
        if self.start_command is not None:
            self.start_command()
        elif self.on_start is not None:
            self.on_start()

    def _pause_clicked(self) -> None:
        print("[AUTONOMOUS][UI] pause button pressed", flush=True)
        self.state.set_enabled(False)
        self._refresh_controls()
        self._notify()
        if self.pause_command is not None:
            self.pause_command()
        elif self.on_pause is not None:
            self.on_pause()

    def _stop_clicked(self) -> None:
        print("[AUTONOMOUS][UI] stop button pressed", flush=True)
        self.state.set_enabled(False)
        self._refresh_controls()
        self._notify()
        if self.stop_command is not None:
            self.stop_command()
        elif self.on_stop is not None:
            self.on_stop()

    def _refresh_controls(self) -> None:
        snapshot = self.state.snapshot()
        autonomous = snapshot.mode is AutonomousRunMode.AUTONOMOUS
        enabled = bool(snapshot.enabled)
        self.interval_combo.configure(state="readonly" if autonomous else "disabled")
        self.start_button.configure(state="normal" if autonomous and not enabled else "disabled")
        self.pause_button.configure(state="normal" if autonomous and enabled else "disabled")
        self.stop_button.configure(state="normal" if autonomous and enabled else "disabled")
        if not autonomous:
            self.status_var.set("Режим анализа: автономное исполнение выключено")
        elif snapshot.message:
            self.status_var.set(f"{snapshot.status}: {snapshot.message}")
        elif enabled:
            self.status_var.set("● АВТОНОМНАЯ ТОРГОВЛЯ РАБОТАЕТ")
        else:
            self.status_var.set("Автономная торговля не запущена")

    def _poll_runtime_state(self) -> None:
        try:
            self._refresh_controls()
        finally:
            if self.frame.winfo_exists():
                self.frame.after(250, self._poll_runtime_state)

    def _notify(self) -> None:
        if self.on_state is not None:
            self.on_state(self.state.snapshot())

    def mode(self) -> ExecutionMode:
        return ExecutionMode.AUTONOMOUS if self.state.snapshot().mode is AutonomousRunMode.AUTONOMOUS else ExecutionMode.ANALYSIS_ONLY

    def interval_minutes(self) -> int:
        return {"1 мин": 1, "5 мин": 5, "15 мин": 15, "30 мин": 30, "1 час": 60}.get(self.interval_var.get(), 5)


__all__ = ["AutonomousControlPanel", "publish_execution_event"]
