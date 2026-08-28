from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any, Callable
import traceback

from edward.services.autonomous_run_state_service import (
    AutonomousRunMode,
    AutonomousRunStateService,
)


def _console(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True, slots=True)
class AutonomousRuntimeConfig:
    interval_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("AUTONOMOUS_INTERVAL_MUST_BE_POSITIVE")


class AutonomousRuntimeService:
    """Own the long-running autonomous lifecycle around one complete cycle callback."""

    def __init__(self, run_cycle: Callable[[], Any], *, state_service: AutonomousRunStateService | None = None, config: AutonomousRuntimeConfig | None = None) -> None:
        self._run_cycle = run_cycle
        self._state = state_service or AutonomousRunStateService()
        self._config = config or AutonomousRuntimeConfig()
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None

    @property
    def state(self) -> AutonomousRunStateService:
        return self._state

    @property
    def config(self) -> AutonomousRuntimeConfig:
        return self._config

    def start(self) -> None:
        if self._state.snapshot().mode is not AutonomousRunMode.AUTONOMOUS:
            raise ValueError("AUTONOMOUS_MODE_REQUIRED")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._state.set_enabled(True)
                self._state.update(status="STARTING", message="Возобновление автономного цикла")
                _console("[AUTONOMOUS][RUNTIME] resume requested")
                return
            self._stop.clear()
            self._state.set_enabled(True)
            self._state.update(status="STARTING", message="Запуск автономного цикла")
            _console(f"[AUTONOMOUS][RUNTIME] starting; interval={self._config.interval_seconds:.1f}s")
            self._thread = Thread(target=self._worker, name="edward-autonomous-runtime", daemon=True)
            self._thread.start()

    def pause(self) -> None:
        with self._lock:
            self._state.set_enabled(False)
            self._state.update(status="PAUSED", message="Автономная торговля на паузе")
            _console("[AUTONOMOUS][RUNTIME] paused")

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            self._state.set_enabled(False)
            self._state.update(status="STOPPED", message="Автономная торговля остановлена")
            _console("[AUTONOMOUS][RUNTIME] stop requested")
        thread = self._thread
        if thread is not None and thread is not __import__("threading").current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            self._thread = None

    def _run_cycle_with_heartbeat(self) -> Any:
        cycle_stop = Event()
        started = monotonic()

        def heartbeat() -> None:
            while not cycle_stop.wait(5.0):
                elapsed = monotonic() - started
                message = f"Выполняется автономный цикл · прошло {elapsed:.0f} сек."
                self._state.update(status="EXECUTING", message=message)
                _console(f"[AUTONOMOUS][HEARTBEAT] {message}")

        thread = Thread(target=heartbeat, name="edward-autonomous-heartbeat", daemon=True)
        thread.start()
        try:
            return self._run_cycle()
        finally:
            cycle_stop.set()
            thread.join(timeout=1.0)

    @staticmethod
    def _cycle_summary(result: Any) -> str:
        """Extract a compact outcome from the facade/controller result for the UI state."""
        control = getattr(result, "control", result)
        reason = str(getattr(control, "reason", "") or "").strip()
        executed = getattr(control, "executed", None)
        if executed is True:
            return f"выполнен: {reason or 'COMPLETED'}"
        if executed is False:
            return f"не выполнен: {reason or 'NOT_EXECUTED'}"
        return "завершён"

    def _worker(self) -> None:
        while not self._stop.is_set():
            snapshot = self._state.snapshot()
            if not snapshot.enabled:
                self._stop.wait(0.25)
                continue

            started = monotonic()
            self._state.update(status="EXECUTING", message="Выполняется автономный цикл · прошло 0 сек.")
            _console("[AUTONOMOUS][RUNTIME] cycle started")
            try:
                result = self._run_cycle_with_heartbeat()
            except Exception as exc:
                self._state.set_enabled(False)
                self._state.update(status="ERROR", message=f"{type(exc).__name__}: {exc}")
                _console(f"[AUTONOMOUS][RUNTIME] cycle failed: {type(exc).__name__}: {exc}")
                traceback.print_exc()
                return

            if self._stop.is_set():
                _console("[AUTONOMOUS][RUNTIME] cycle interrupted by stop")
                return
            if not self._state.snapshot().enabled:
                _console("[AUTONOMOUS][RUNTIME] cycle ended while runtime disabled")
                continue

            elapsed = monotonic() - started
            remaining = max(0.0, self._config.interval_seconds - elapsed)
            summary = self._cycle_summary(result)
            self._state.update(status="WAITING", message=f"Последний цикл {summary}. Следующий анализ через {remaining:.0f} сек.")
            _console(f"[AUTONOMOUS][RUNTIME] cycle completed; outcome={summary}; elapsed={elapsed:.1f}s; next_cycle_in={remaining:.1f}s")
            if self._stop.wait(remaining):
                return


__all__ = ["AutonomousRuntimeService", "AutonomousRuntimeConfig"]
