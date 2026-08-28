from __future__ import annotations

from dataclasses import dataclass

from edward.domain.execution import ExecutionMode
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_run_state_service import AutonomousRunState


@dataclass(frozen=True, slots=True)
class AutonomousExecutionAuthorization:
    allowed: bool
    reason: str


class AutonomousExecutionAuthorizationService:
    """Final explicit gate before the autonomous controller may execute a plan."""

    def authorize(
        self,
        *,
        state: AutonomousRunState,
        mode: ExecutionMode,
        plan: AutonomousExecutionPlan,
    ) -> AutonomousExecutionAuthorization:
        if mode is not ExecutionMode.AUTONOMOUS:
            return AutonomousExecutionAuthorization(False, "AUTONOMOUS_MODE_REQUIRED")
        if not state.enabled:
            return AutonomousExecutionAuthorization(False, "AUTONOMOUS_TRADING_DISABLED")
        if not plan.steps:
            return AutonomousExecutionAuthorization(False, "EMPTY_EXECUTION_PLAN")
        return AutonomousExecutionAuthorization(True, "AUTHORIZED")


__all__ = ["AutonomousExecutionAuthorization", "AutonomousExecutionAuthorizationService"]
