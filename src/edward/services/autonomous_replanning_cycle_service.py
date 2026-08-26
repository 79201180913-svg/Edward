from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_execution_verification_service import ExecutionVerification


@dataclass(frozen=True, slots=True)
class AutonomousReplanningCycleResult:
    completed: bool
    iterations: int
    executed_steps: tuple[int, ...]
    stopped_reason: str | None = None


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
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self._refresh_state = refresh_state
        self._build_plan = build_plan
        self._execute_step = execute_step
        self._verify_step = verify_step
        self._max_iterations = max_iterations

    def run(self) -> AutonomousReplanningCycleResult:
        executed: list[int] = []
        state = self._refresh_state()

        for iteration in range(1, self._max_iterations + 1):
            plan = self._build_plan(state)
            if not plan.steps:
                return AutonomousReplanningCycleResult(True, iteration, tuple(executed))

            step = plan.steps[0]
            try:
                execution = self._execute_step(step)
            except Exception as exc:
                return AutonomousReplanningCycleResult(
                    False, iteration, tuple(executed), f"EXECUTION_ERROR:{exc}"
                )

            try:
                refreshed_state = self._refresh_state()
                verification = self._verify_step(step, execution, refreshed_state)
            except Exception as exc:
                return AutonomousReplanningCycleResult(
                    False, iteration, tuple(executed), f"VERIFICATION_ERROR:{exc}"
                )

            if not verification.passed:
                return AutonomousReplanningCycleResult(
                    False,
                    iteration,
                    tuple(executed),
                    "VERIFICATION_FAILED:" + ";".join(verification.reasons),
                )

            executed.append(int(step.sequence))
            # The verified refreshed state is authoritative for the next plan.
            # Do not refresh it again before rebuilding: that would introduce a
            # second state transition and could cause the next plan to be built
            # from a different account snapshot than the one just verified.
            state = refreshed_state

        return AutonomousReplanningCycleResult(
            False,
            self._max_iterations,
            tuple(executed),
            "MAX_ITERATIONS_REACHED",
        )


__all__ = ["AutonomousReplanningCycleResult", "AutonomousReplanningCycleService"]
