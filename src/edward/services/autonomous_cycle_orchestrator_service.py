from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_replanning_cycle_service import AutonomousReplanningCycleResult, AutonomousReplanningCycleService
from edward.services.budget_planning_service import BudgetPlan


@dataclass(frozen=True, slots=True)
class AutonomousCycleOrchestrationResult:
    completed: bool
    stage: str
    replanning: AutonomousReplanningCycleResult | None = None
    reason: str = ""


class AutonomousCycleOrchestratorService:
    """Own the v0.7 autonomous lifecycle: state -> recovery gate -> plan -> execute -> verify -> replan."""

    def __init__(self, *, refresh_state: Callable[[], AccountState], reconcile_protection: Callable[[AccountState], tuple[bool, tuple[str, ...]]], recover_protection: Callable[[AccountState], tuple[bool, tuple[str, ...]]] | None = None, build_plan: Callable[[AccountState], AutonomousExecutionPlan], budget_for_state: Callable[[AccountState], BudgetPlan], execute_step: Callable[[Any, AccountState, BudgetPlan], Any], verify_step: Callable[[Any, Any, AccountState], Any], max_iterations: int = 50) -> None:
        self._refresh = refresh_state
        self._reconcile = reconcile_protection
        self._recover = recover_protection
        self._build_plan = build_plan
        self._budget = budget_for_state
        self._execute = execute_step
        self._verify = verify_step
        self._max_iterations = max_iterations

    def run(self) -> AutonomousCycleOrchestrationResult:
        try:
            state = self._refresh()
        except Exception as exc:
            return AutonomousCycleOrchestrationResult(False, "STATE", reason=f"STATE_REFRESH_FAILED:{exc}")

        protected, reasons = self._reconcile(state)
        if not protected and self._recover is not None:
            recovered, recovery_reasons = self._recover(state)
            if not recovered:
                return AutonomousCycleOrchestrationResult(False, "PROTECTION", reason="PROTECTION_RECOVERY_FAILED:" + ";".join(recovery_reasons))
            state = self._refresh()
            protected, reasons = self._reconcile(state)

        if not protected:
            return AutonomousCycleOrchestrationResult(False, "PROTECTION", reason="PROTECTION_RECONCILIATION_FAILED:" + ";".join(reasons))

        def build_checked(current: AccountState) -> AutonomousExecutionPlan:
            return self._build_plan(current)

        def execute_checked(step: Any) -> Any:
            current = self._refresh()
            protected_now, reasons_now = self._reconcile(current)
            if not protected_now:
                raise RuntimeError("PROTECTION_RECONCILIATION_FAILED:" + ";".join(reasons_now))
            return self._execute(step, current, self._budget(current))

        cycle = AutonomousReplanningCycleService(refresh_state=self._refresh, build_plan=build_checked, execute_step=execute_checked, verify_step=self._verify, max_iterations=self._max_iterations).run()
        return AutonomousCycleOrchestrationResult(cycle.completed, "REPLANNING", cycle, cycle.stopped_reason or "")


__all__ = ["AutonomousCycleOrchestrationResult", "AutonomousCycleOrchestratorService"]
