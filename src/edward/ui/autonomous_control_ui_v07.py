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
    """Reusable control panel for the v0.7 autonomous runtime state."""

    def __init__(self, parent: Any, *, state_service: AutonomousRunStateService | None = None, on_state: Callable[[Any], None] | None = None) -> None:
        self.state = state_service or AutonomousRunStateService()
        self.on_state = on_state
        self.frame = ttk.LabelFrame(parent, text="Режим автономной торговли", padding=10)
        self.mode_var = tk.StringVar(value="analysis")
        self.enabled_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Готово")

        ttk.Radiobutton(self.frame, text="Только анализ", value="analysis", variable=self.mode_var, command=self._mode_changed).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(self.frame, text="Автономная торговля", value="autonomous", variable=self.mode_var, command=self._mode_changed).pack(side="left", padx=(0, 10))
        self.enable_button = ttk.Checkbutton(self.frame, text="Включить исполнение", variable=self.enabled_var, command=self._enabled_changed)
        self.enable_button.pack(side="left", padx=(0, 12))
        ttk.Label(self.frame, textvariable=self.status_var).pack(side="left")

        self._refresh_controls()

    def pack(self, **kwargs: Any) -> None:
        self.frame.pack(**kwargs)

    def grid(self, **kwargs: Any) -> None:
        self.frame.grid(**kwargs)

    def _mode_changed(self) -> None:
        mode = AutonomousRunMode.AUTONOMOUS if self.mode_var.get() == "autonomous" else AutonomousRunMode.ANALYSIS
        self.state.set_mode(mode)
        self._refresh_controls()
        self._notify()

    def _enabled_changed(self) -> None:
        self.state.set_enabled(bool(self.enabled_var.get()))
        self._refresh_controls()
        self._notify()

    def _refresh_controls(self) -> None:
        snapshot = self.state.snapshot()
        self.enabled_var.set(snapshot.enabled)
        if snapshot.mode is AutonomousRunMode.AUTONOMOUS:
            self.enable_button.configure(state="normal")
            self.status_var.set("Автономный режим: исполнение " + ("ВКЛ" if snapshot.enabled else "ВЫКЛ"))
        else:
            self.enable_button.configure(state="disabled")
            self.status_var.set("Режим анализа: заявки не отправляются")

    def _notify(self) -> None:
        if self.on_state is not None:
            self.on_state(self.state.snapshot())

    def mode(self) -> ExecutionMode:
        return ExecutionMode.AUTONOMOUS if self.state.snapshot().mode is AutonomousRunMode.AUTONOMOUS else ExecutionMode.ANALYSIS_ONLY


__all__ = ["AutonomousControlPanel"]
