from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_execution_preflight_service import AutonomousExecutionPreflightService
from edward.services.autonomous_execution_sequence_service import AutonomousExecutionPhase, AutonomousExecutionPhaseEvent, AutonomousExecutionSequenceResult, AutonomousExecutionSequenceService
from edward.services.autonomous_replanning_cycle_service import AutonomousReplanningCycleResult, AutonomousReplanningCycleService
from edward.services.budget_planning_service import BudgetPlan
from edward.services.protection_reconciliation_service import ProtectionReconciliationService


@dataclass(frozen=True, slots=True)
class AutonomousTradingControlResult:
    mode: ExecutionMode
    executed: bool
    reason: str
    phase: AutonomousExecutionPhase = AutonomousExecutionPhase.STOPPED
    sequence: AutonomousExecutionSequenceResult | None = None
    replanning: AutonomousReplanningCycleResult | None = None
    preflight_reasons: tuple[str, ...] = ()
    events: tuple[AutonomousExecutionPhaseEvent, ...] = ()


class AutonomousTradingController:
    def __init__(self, sequence_service: AutonomousExecutionSequenceService, *, preflight_service: AutonomousExecutionPreflightService | None = None, protection_reconciliation: ProtectionReconciliationService | None = None) -> None:
        self._sequence = sequence_service
        self._preflight = preflight_service or AutonomousExecutionPreflightService()
        self._protection_reconciliation = protection_reconciliation
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def _gate(self, *, account_id: str, mode: ExecutionMode, plan: AutonomousExecutionPlan, budget: BudgetPlan | None, state: AccountState | None) -> tuple[bool, str, tuple[str, ...]]:
        if mode is not ExecutionMode.AUTONOMOUS:
            return False, "AUTONOMOUS_MODE_REQUIRED", ()
        if not self._enabled:
            return False, "AUTONOMOUS_TRADING_DISABLED", ()
        if not plan.steps:
            return False, "EMPTY_EXECUTION_PLAN", ()
        if budget is None or state is None:
            return False, "FRESH_ACCOUNT_STATE_REQUIRED", ()
        if self._protection_reconciliation is not None:
            reconciliation = self._protection_reconciliation.reconcile(account_id=account_id, positions=state.positions)
            if not reconciliation.protected:
                return False, "PROTECTION_RECONCILIATION_FAILED", reconciliation.reasons
        preflight = self._preflight.validate(plan=plan, budget=budget, state=state)
        if not preflight.passed:
            return False, "PREFLIGHT_REJECTED", preflight.reasons
        return True, "", ()

    def _execute_sequence(self, *, account_id: str, plan: AutonomousExecutionPlan, result_factory: Callable[[Any], Any], mode: ExecutionMode) -> AutonomousExecutionSequenceResult:
        try:
            return self._sequence.execute_confirmed_plan(account_id=account_id, plan=plan, result_factory=result_factory, mode=mode)
        except TypeError as exc:
            if "unexpected keyword argument 'mode'" not in str(exc):
                raise
            return self._sequence.execute_confirmed_plan(account_id=account_id, plan=plan, result_factory=result_factory)

    def execute(self, *, account_id: str, plan: AutonomousExecutionPlan, result_factory: Callable[[Any], Any], mode: ExecutionMode = ExecutionMode.ANALYSIS_ONLY, budget: BudgetPlan | None = None, state: AccountState | None = None) -> AutonomousTradingControlResult:
        allowed, reason, reasons = self._gate(account_id=account_id, mode=mode, plan=plan, budget=budget, state=state)
        if not allowed:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason=reason, preflight_reasons=reasons)
        sequence = self._execute_sequence(account_id=account_id, plan=plan, result_factory=result_factory, mode=mode)
        return AutonomousTradingControlResult(mode=mode, executed=sequence.completed, reason="COMPLETED" if sequence.completed else f"STOPPED_AT:{sequence.stopped_at}", phase=getattr(sequence, "phase", AutonomousExecutionPhase.STOPPED), sequence=sequence, events=getattr(sequence, "events", ()))

    def execute_replanned(self, *, account_id: str, mode: ExecutionMode, refresh_state: Callable[[], AccountState], build_plan: Callable[[AccountState], AutonomousExecutionPlan], budget_for_state: Callable[[AccountState], BudgetPlan], result_factory: Callable[[Any], Any], max_iterations: int = 50) -> AutonomousTradingControlResult:
        if mode is not ExecutionMode.AUTONOMOUS:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="AUTONOMOUS_MODE_REQUIRED")
        if not self._enabled:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="AUTONOMOUS_TRADING_DISABLED")
        preflight_reasons: list[str] = []
        cycle_error: list[str] = []

        def build_checked_plan(state: AccountState) -> AutonomousExecutionPlan:
            plan = build_plan(state)
            if not plan.steps:
                return plan
            budget = budget_for_state(state)
            allowed, reason, reasons = self._gate(account_id=account_id, mode=mode, plan=plan, budget=budget, state=state)
            if not allowed:
                preflight_reasons.extend(reasons or (reason,))
                cycle_error.append(reason + (":" + ";".join(reasons) if reasons else ""))
                return AutonomousExecutionPlan(steps=())
            return plan

        def execute_one(step: Any) -> Any:
            sequence = self._execute_sequence(account_id=account_id, plan=AutonomousExecutionPlan(steps=(step,)), result_factory=result_factory, mode=mode)
            if not sequence.steps:
                raise RuntimeError("EXECUTION_SEQUENCE_EMPTY")
            item = sequence.steps[0]
            if not item.completed:
                raise RuntimeError(item.reason or "EXECUTION_STEP_FAILED")
            return item

        def verify_one(step: Any, execution: Any, state: AccountState) -> Any:
            verification = getattr(execution, "verification", None)
            if verification is None:
                raise RuntimeError("VERIFICATION_RESULT_MISSING")
            return verification

        cycle = AutonomousReplanningCycleService(refresh_state=refresh_state, build_plan=build_checked_plan, execute_step=execute_one, verify_step=verify_one, max_iterations=max_iterations).run()
        if cycle_error:
            reason = "EXECUTION_ERROR:" + cycle_error[-1]
        elif cycle.completed:
            reason = "COMPLETED"
        else:
            reason = cycle.stopped_reason or "STOPPED"
        return AutonomousTradingControlResult(mode=mode, executed=bool(cycle.executed_steps), reason=reason, phase=AutonomousExecutionPhase.COMPLETED if cycle.completed else AutonomousExecutionPhase.STOPPED, replanning=cycle, preflight_reasons=tuple(preflight_reasons))


__all__ = ["AutonomousTradingControlResult", "AutonomousTradingController"]
