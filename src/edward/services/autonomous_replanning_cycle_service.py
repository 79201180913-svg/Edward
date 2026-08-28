from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_execution_verification_service import ExecutionVerification


def _console(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True, slots=True)
class AutonomousReplanningCycleResult:
    completed: bool
    iterations: int
    executed_steps: tuple[int, ...]
    stopped_reason: str | None = None


class AutonomousReplanningCycleService:
    """Run one execution step, verify it, then discard and rebuild the plan."""

    def __init__(self, *, refresh_state: Callable[[], Any], build_plan: Callable[[Any], AutonomousExecutionPlan], execute_step: Callable[[Any], Any], verify_step: Callable[[Any, Any, Any], ExecutionVerification], max_iterations: int = 50) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self._refresh_state = refresh_state
        self._build_plan = build_plan
        self._execute_step = execute_step
        self._verify_step = verify_step
        self._max_iterations = max_iterations

    def run(self) -> AutonomousReplanningCycleResult:
        executed: list[int] = []
        _console(f"[AUTONOMOUS][REPLAN] loop START max_iterations={self._max_iterations}")
        state = self._refresh_state()

        for iteration in range(1, self._max_iterations + 1):
            _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} build plan: START")
            plan = self._build_plan(state)
            _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} plan ready steps={len(plan.steps)}")
            if not plan.steps:
                _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} no executable steps; FINISHED")
                return AutonomousReplanningCycleResult(True, iteration, tuple(executed))

            step = plan.steps[0]
            ticker = getattr(step, "ticker", "")
            target_value = getattr(step, "target_value", "")
            _console(f"[AUTONOMOUS][EXECUTION] iteration={iteration} step={step.sequence} action={step.action} ticker={ticker} uid={step.instrument_uid} target_value={target_value}")
            try:
                execution = self._execute_step(step)
                _console(f"[AUTONOMOUS][EXECUTION] iteration={iteration} step={step.sequence} execution returned")
            except Exception as exc:
                reason = f"EXECUTION_ERROR:{exc}"
                _console(f"[AUTONOMOUS][EXECUTION] iteration={iteration} step={step.sequence} FAILED reason={reason}")
                return AutonomousReplanningCycleResult(False, iteration, tuple(executed), reason)

            try:
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence}: refresh state START")
                refreshed_state = self._refresh_state()
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence}: verify START")
                verification = self._verify_step(step, execution, refreshed_state)
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence}: passed={verification.passed} reasons={';'.join(verification.reasons) if verification.reasons else 'NONE'}")
            except Exception as exc:
                reason = f"VERIFICATION_ERROR:{exc}"
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence} FAILED reason={reason}")
                return AutonomousReplanningCycleResult(False, iteration, tuple(executed), reason)

            if not verification.passed:
                reason = "VERIFICATION_FAILED:" + ";".join(verification.reasons)
                _console(f"[AUTONOMOUS][VERIFY] iteration={iteration} step={step.sequence} REJECTED reason={reason}")
                return AutonomousReplanningCycleResult(False, iteration, tuple(executed), reason)

            executed.append(int(step.sequence))
            _console(f"[AUTONOMOUS][REPLAN] iteration={iteration} step={step.sequence} verified; rebuilding plan from refreshed state")
            state = refreshed_state

        reason = "MAX_ITERATIONS_REACHED"
        _console(f"[AUTONOMOUS][REPLAN] loop STOP reason={reason}")
        return AutonomousReplanningCycleResult(False, self._max_iterations, tuple(executed), reason)


__all__ = ["AutonomousReplanningCycleResult", "AutonomousReplanningCycleService"]
