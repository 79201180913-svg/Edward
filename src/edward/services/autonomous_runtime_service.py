from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable

from edward.services.autonomous_run_state_service import (
    AutonomousRunMode,
    AutonomousRunStateService,
)


@dataclass(frozen=True, slots=True)
class AutonomousRuntimeConfig:
    interval_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("AUTONOMOUS_INTERVAL_MUST_BE_POSITIVE")


class AutonomousRuntimeService:
    """Own the long-running autonomous lifecycle around one complete cycle callback."""

    def __init__(self, run_cycle: Callable[[], None], *, state_service: AutonomousRunStateService | None = None, config: AutonomousRuntimeConfig | None = None) -> None:
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
                return
            self._stop.clear()
            self._state.set_enabled(True)
            self._state.update(status="STARTING", message="Запуск автономного цикла")
            self._thread = Thread(target=self._worker, name="edward-autonomous-runtime", daemon=True)
            self._thread.start()

    def pause(self) -> None:
        with self._lock:
            self._state.set_enabled(False)
            self._state.update(status="PAUSED", message="Автономная торговля на паузе")

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            self._state.set_enabled(False)
            self._state.update(status="STOPPED", message="Автономная торговля остановлена")
        thread = self._thread
        if thread is not None and thread is not __import__("threading").current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            self._thread = None

    def _run_cycle_with_heartbeat(self) -> None:
        """Run one cycle while continuously exposing elapsed time to the UI."""
        cycle_stop = Event()
        started = monotonic()

        def heartbeat() -> None:
            while not cycle_stop.wait(1.0):
                elapsed = monotonic() - started
                self._state.update(
                    status="EXECUTING",
                    message=f"Выполняется автономный цикл · прошло {elapsed:.0f} сек.",
                )

        heartbeat_thread = Thread(
            target=heartbeat,
            name="edward-autonomous-heartbeat",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            self._run_cycle()
        finally:
            cycle_stop.set()
            heartbeat_thread.join(timeout=1.0)

    def _worker(self) -> None:
        while not self._stop.is_set():
            snapshot = self._state.snapshot()
            if not snapshot.enabled:
                self._stop.wait(0.25)
                continue

            started = monotonic()
            self._state.update(status="EXECUTING", message="Выполняется автономный цикл · прошло 0 сек.")
            try:
                self._run_cycle_with_heartbeat()
            except Exception as exc:
                self._state.set_enabled(False)
                self._state.update(status="ERROR", message=f"{type(exc).__name__}: {exc}")
                return

            if self._stop.is_set():
                return
            if not self._state.snapshot().enabled:
                continue

            elapsed = monotonic() - started
            remaining = max(0.0, self._config.interval_seconds - elapsed)
            self._state.update(status="WAITING", message=f"Следующий анализ через {remaining:.0f} сек.")
            if self._stop.wait(remaining):
                return


__all__ = ["AutonomousRuntimeService", "AutonomousRuntimeConfig"]