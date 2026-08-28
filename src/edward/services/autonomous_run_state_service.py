from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Lock


class AutonomousRunMode(StrEnum):
    ANALYSIS = "analysis"
    AUTONOMOUS = "autonomous"


@dataclass(frozen=True, slots=True)
class AutonomousRunState:
    mode: AutonomousRunMode = AutonomousRunMode.ANALYSIS
    enabled: bool = False
    status: str = "READY"
    execution_id: str | None = None
    message: str = ""


class AutonomousRunStateService:
    """Thread-safe state boundary for the autonomous UI/runtime control."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._state = AutonomousRunState()

    def snapshot(self) -> AutonomousRunState:
        with self._lock:
            return self._state

    def set_mode(self, mode: AutonomousRunMode) -> AutonomousRunState:
        with self._lock:
            self._state = AutonomousRunState(
                mode=mode,
                enabled=self._state.enabled if mode is AutonomousRunMode.AUTONOMOUS else False,
                status="READY",
                execution_id=self._state.execution_id,
                message="",
            )
            return self._state

    def set_enabled(self, enabled: bool) -> AutonomousRunState:
        with self._lock:
            if enabled and self._state.mode is not AutonomousRunMode.AUTONOMOUS:
                raise ValueError("AUTONOMOUS_MODE_REQUIRED")
            self._state = AutonomousRunState(
                mode=self._state.mode,
                enabled=bool(enabled),
                status="READY",
                execution_id=self._state.execution_id,
                message="",
            )
            return self._state

    def update(self, *, status: str, message: str = "", execution_id: str | None = None) -> AutonomousRunState:
        with self._lock:
            self._state = AutonomousRunState(
                mode=self._state.mode,
                enabled=self._state.enabled,
                status=status,
                execution_id=execution_id if execution_id is not None else self._state.execution_id,
                message=message,
            )
            return self._state


__all__ = ["AutonomousRunMode", "AutonomousRunState", "AutonomousRunStateService"]
