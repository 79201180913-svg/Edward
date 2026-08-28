from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from edward.domain.execution import ExecutionMode
from edward.services.autonomous_run_state_service import (
    AutonomousRunMode,
    AutonomousRunStateService,
)


class AutonomousControlPanel:
    """Explicit controls and runtime state for the v0.7 autonomous mode."""

    def __init__(
        self,
        parent: Any,
        *,
        state_service: AutonomousRunStateService | None = None,
        on_state: Callable[[Any], None] | None = None,
        on_start: Callable[[], None] | None = None,
        on_pause: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        self.state = state_service or AutonomousRunStateService()
        self.on_state = on_state
        self.on_start = on_start
        self.on_pause = on_pause
        self.on_stop = on_stop
        self.start_command: Callable[[], None] | None = None
        self.pause_command: Callable[[], None] | None = None
        self.stop_command: Callable[[], None] | None = None
        self.frame = ttk.LabelFrame(parent, text="Режим автономной торговли", padding=10)
        self.mode_var = tk.StringVar(value="analysis")
        self.interval_var = tk.StringVar(value="5 мин")
        self.status_var = tk.StringVar(value="Готово")

        ttk.Radiobutton(
            self.frame,
            text="Только анализ",
            value="analysis",
            variable=self.mode_var,
            command=self._mode_changed,
        ).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(
            self.frame,
            text="Автономная торговля",
            value="autonomous",
            variable=self.mode_var,
            command=self._mode_changed,
        ).pack(side="left", padx=(0, 12))

        ttk.Label(self.frame, text="Интервал:").pack(side="left")
        self.interval_combo = ttk.Combobox(
            self.frame,
            textvariable=self.interval_var,
            state="readonly",
            values=("1 мин", "5 мин", "15 мин", "30 мин", "1 час"),
            width=8,
        )
        self.interval_combo.pack(side="left", padx=(5, 12))
        self.interval_combo.bind("<<ComboboxSelected>>", self._interval_changed)

        self.start_button = ttk.Button(
            self.frame,
            text="▶ Запустить автономную торговлю",
            command=self._start_clicked,
        )
        self.start_button.pack(side="left", padx=(0, 6))
        self.pause_button = ttk.Button(
            self.frame,
            text="⏸ Пауза",
            command=self._pause_clicked,
        )
        self.pause_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(
            self.frame,
            text="■ Остановить",
            command=self._stop_clicked,
        )
        self.stop_button.pack(side="left", padx=(0, 12))

        ttk.Label(self.frame, textvariable=self.status_var).pack(side="left")
        self._refresh_controls()

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
        self._notify()

    def _start_clicked(self) -> None:
        self.state.set_enabled(True)
        self._refresh_controls()
        self._notify()
        if self.start_command is not None:
            self.start_command()
        elif self.on_start is not None:
            self.on_start()

    def _pause_clicked(self) -> None:
        self.state.set_enabled(False)
        self._refresh_controls()
        self._notify()
        if self.pause_command is not None:
            self.pause_command()
        elif self.on_pause is not None:
            self.on_pause()

    def _stop_clicked(self) -> None:
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
        elif enabled:
            self.status_var.set("● АВТОНОМНАЯ ТОРГОВЛЯ РАБОТАЕТ")
        else:
            self.status_var.set("Автономная торговля не запущена")

    def _notify(self) -> None:
        if self.on_state is not None:
            self.on_state(self.state.snapshot())

    def mode(self) -> ExecutionMode:
        return ExecutionMode.AUTONOMOUS if self.state.snapshot().mode is AutonomousRunMode.AUTONOMOUS else ExecutionMode.ANALYSIS_ONLY

    def interval_minutes(self) -> int:
        return {
            "1 мин": 1,
            "5 мин": 5,
            "15 мин": 15,
            "30 мин": 30,
            "1 час": 60,
        }.get(self.interval_var.get(), 5)


__all__ = ["AutonomousControlPanel"]
