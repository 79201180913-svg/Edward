from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_execution_verification_service import ExecutionVerification


def _console(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True, slots=True)
class AutonomousExecutionLifecycleEvent:
    sequence: int
    action: str
    ticker: str
    status: str
    message: str = ""
    execution_id: str | None = None


@dataclass(frozen=True, slots=True)
class AutonomousReplanningCycleResult:
    completed: bool
    iterations: int
    executed_steps: tuple[int, ...]
    stopped_reason: str | None = None
    lifecycle_events: tuple[AutonomousExecutionLifecycleEvent, ...] = ()


class AutonomousReplanningCycleService:
    """Run one execution step, verify it, then discard and rebuild the plan."""

    def __init__(
        self,
        *,
        refresh_state: Callable[[], Any],
        build_plan: Callable[[Any], AutonomousExecutionPlan],
        execute_step: Callable[[Any], Any],
        verify_step: Callable[[Any, Any, Any], ExecutionVerification],
        max_iterations: int = 50,
        lifecycle_callback: Callable[[AutonomousExecutionLifecycleEvent], None] | None = None,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self._refresh_state = refresh_state
        self._build_plan = build_plan
        self._execute_step = execute_step
        self._verify_step = verify_step
        self._max_iterations = max_iterations
        self._lifecycle_callback = lifecycle_callback

    def _emit(self, events: list[AutonomousExecutionLifecycleEvent], step: Any, status: str, message: str = "", execution_id: str | None = None) -> None:
        event = AutonomousExecutionLifecycleEvent(
            int(step.sequence),
            str(getattr(step, "action", "")),
            str(getattr(step, "ticker", "")),
            status,
            message,
            execution_id,
        )
        events.append(event)
        if self._lifecycle_callback is not None:
            self._lifecycle_callback(event)

    def run(self) -> AutonomousReplanningCycleResult:
        executed: list[int] = []
        lifecycle: list[AutonomousExecutionLifecycleEvent] = []
        _console(f"[AUTONOMOUS][REPLAN] loop START max_iterations={self._max_iterations}")
        state = self._refresh_state()

        for iteration in range(1, self._max_iterations + 1):
            _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} build plan: START")
            plan = self._build_plan(state)
            _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} plan ready steps={len(plan.steps)}")
            if not plan.steps:
                _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} no executable steps; FINISHED")
                return AutonomousReplanningCycleResult(True, iteration, tuple(executed), lifecycle_events=tuple(lifecycle))

            step = plan.steps[0]
            ticker = getattr(step, "ticker", "")
            target_value = getattr(step, "target_value", "")
            _console(f"[AUTONOMOUS][EXECUTION] iteration={iteration} step={step.sequence} action={step.action} ticker={ticker} uid={step.instrument_uid} target_value={target_value}")
            self._emit(lifecycle, step, "PLAN", "Шаг выбран для исполнения")
            try:
                self._emit(lifecycle, step, "SUBMITTING", "Подготовка и отправка заявки")
                execution = self._execute_step(step)
                execution_id = getattr(execution, "execution_id", None)
                execution_status = getattr(getattr(execution, "status", None), "value", getattr(execution, "status", None))
                self._emit(lifecycle, step, "SUBMITTED", f"Заявка принята; status={execution_status}", execution_id)
                _console(f"[AUTONOMOUS][EXECUTION] iteration={iteration} step={step.sequence} execution returned")
            except Exception as exc:
                reason = f"EXECUTION_ERROR:{exc}"
                self._emit(lifecycle, step, "FAILED", reason)
                _console(f"[AUTONOMOUS][EXECUTION] iteration={iteration} step={step.sequence} FAILED reason={reason}")
                return AutonomousReplanningCycleResult(False, iteration, tuple(executed), reason, tuple(lifecycle))

            self._emit(lifecycle, step, "VERIFYING", "Проверка фактического состояния счёта", execution_id)
            try:
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence}: refresh state START")
                refreshed_state = self._refresh_state()
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence}: verify START")
                verification = self._verify_step(step, execution, refreshed_state)
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence}: passed={verification.passed} reasons={';'.join(verification.reasons) if verification.reasons else 'NONE'}")
            except Exception as exc:
                reason = f"VERIFICATION_ERROR:{exc}"
                self._emit(lifecycle, step, "FAILED", reason, execution_id)
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence} FAILED reason={reason}")
                return AutonomousReplanningCycleResult(False, iteration, tuple(executed), reason, tuple(lifecycle))

            if not verification.passed:
                reason = "VERIFICATION_FAILED:" + ";".join(verification.reasons)
                self._emit(lifecycle, step, "FAILED", reason, execution_id)
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence} REJECTED reason={reason}")
                return AutonomousReplanningCycleResult(False, iteration, tuple(executed), reason, tuple(lifecycle))

            self._emit(lifecycle, step, "EXECUTED", "Сделка подтверждена проверкой состояния счёта", execution_id)
            executed.append(int(step.sequence))
            _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} step={step.sequence} verified; rebuilding plan from refreshed state")
            # The verified refreshed state is authoritative for the next plan.
            state = refreshed_state

        reason = "MAX_ITERATIONS_REACHED"
        _console(f"[AUTONOMOUS][REPLAN] loop STOP reason={reason}")
        return AutonomousReplanningCycleResult(False, self._max_iterations, tuple(executed), reason, tuple(lifecycle))


__all__ = ["AutonomousExecutionLifecycleEvent", "AutonomousReplanningCycleResult", "AutonomousReplanningCycleService"]
