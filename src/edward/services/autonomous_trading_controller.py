from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_execution_preflight_service import AutonomousExecutionPreflightService
from edward.services.autonomous_execution_sequence_service import (
    AutonomousExecutionPhase,
    AutonomousExecutionPhaseEvent,
    AutonomousExecutionSequenceResult,
    AutonomousExecutionSequenceService,
)
from edward.services.autonomous_replanning_cycle_service import (
    AutonomousReplanningCycleResult,
    AutonomousReplanningCycleService,
)
from edward.services.budget_planning_service import BudgetPlan


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
    """Explicit gate between autonomous planning and real submission."""

    def __init__(
        self,
        sequence_service: AutonomousExecutionSequenceService,
        *,
        preflight_service: AutonomousExecutionPreflightService | None = None,
    ) -> None:
        self._sequence = sequence_service
        self._preflight = preflight_service or AutonomousExecutionPreflightService()
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def _gate(
        self,
        *,
        mode: ExecutionMode,
        plan: AutonomousExecutionPlan,
        budget: BudgetPlan | None,
        state: AccountState | None,
    ) -> tuple[bool, str, tuple[str, ...]]:
        if mode is not ExecutionMode.AUTONOMOUS:
            return False, "AUTONOMOUS_MODE_REQUIRED", ()
        if not self._enabled:
            return False, "AUTONOMOUS_TRADING_DISABLED", ()
        if not plan.steps:
            return False, "EMPTY_EXECUTION_PLAN", ()
        if budget is None or state is None:
            return False, "FRESH_ACCOUNT_STATE_REQUIRED", ()
        preflight = self._preflight.validate(plan=plan, budget=budget, state=state)
        if not preflight.passed:
            return False, "PREFLIGHT_REJECTED", preflight.reasons
        return True, "", ()

    def execute(
        self,
        *,
        account_id: str,
        plan: AutonomousExecutionPlan,
        result_factory: Callable[[Any], Any],
        mode: ExecutionMode = ExecutionMode.ANALYSIS_ONLY,
        budget: BudgetPlan | None = None,
        state: AccountState | None = None,
    ) -> AutonomousTradingControlResult:
        allowed, reason, reasons = self._gate(mode=mode, plan=plan, budget=budget, state=state)
        if not allowed:
            return AutonomousTradingControlResult(
                mode=mode,
                executed=False,
                reason=reason,
                preflight_reasons=reasons,
            )

        sequence = self._sequence.execute_confirmed_plan(
            account_id=account_id,
            plan=plan,
            result_factory=result_factory,
        )
        return AutonomousTradingControlResult(
            mode=mode,
            executed=sequence.completed,
            reason="COMPLETED" if sequence.completed else f"STOPPED_AT:{sequence.stopped_at}",
            phase=getattr(sequence, "phase", AutonomousExecutionPhase.STOPPED),
            sequence=sequence,
            events=getattr(sequence, "events", ()),
        )

    def execute_replanned(
        self,
        *,
        mode: ExecutionMode,
        refresh_state: Callable[[], AccountState],
        build_plan: Callable[[AccountState], AutonomousExecutionPlan],
        budget_for_state: Callable[[AccountState], BudgetPlan],
        result_factory: Callable[[Any], Any],
        max_iterations: int = 50,
    ) -> AutonomousTradingControlResult:
        """Run the autonomous step -> refresh -> verify -> replan loop.

        Every newly built plan is preflighted against the exact account snapshot
        used to build it. Only the first step is submitted; after verification
        the verified snapshot becomes the input for the next planning pass.
        """
        if mode is not ExecutionMode.AUTONOMOUS:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="AUTONOMOUS_MODE_REQUIRED")
        if not self._enabled:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="AUTONOMOUS_TRADING_DISABLED")

        preflight_reasons: list[str] = []
        stopped_reason: list[str] = []

        def build_checked_plan(state: AccountState) -> AutonomousExecutionPlan:
            plan = build_plan(state)
            budget = budget_for_state(state)
            allowed, reason, reasons = self._gate(
                mode=mode, plan=plan, budget=budget, state=state
            )
            if not allowed:
                preflight_reasons.extend(reasons or (reason,))
                if not plan.steps and reason == "EMPTY_EXECUTION_PLAN":
                    return plan
                raise RuntimeError(reason + (":" + ";".join(reasons) if reasons else ""))
            return plan

        def execute_one(step: Any) -> Any:
            one_step_plan = AutonomousExecutionPlan(steps=(step,))
            sequence = self._sequence.execute_confirmed_plan(
                account_id=getattr(step, "account_id", ""),
                plan=one_step_plan,
                result_factory=result_factory,
            )
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

        try:
            cycle = AutonomousReplanningCycleService(
                refresh_state=refresh_state,
                build_plan=build_checked_plan,
                execute_step=execute_one,
                verify_step=verify_one,
                max_iterations=max_iterations,
            ).run()
        except Exception as exc:
            stopped_reason.append(str(exc))
            cycle = AutonomousReplanningCycleResult(
                completed=False, iterations=0, executed_steps=(), stopped_reason=str(exc)
            )

        reason = "COMPLETED" if cycle.completed else (cycle.stopped_reason or "STOPPED")
        if preflight_reasons and cycle.stopped_reason and cycle.stopped_reason.startswith("EXECUTION_ERROR:"):
            reason = cycle.stopped_reason
        return AutonomousTradingControlResult(
            mode=mode,
            executed=bool(cycle.executed_steps),
            reason=reason,
            phase=AutonomousExecutionPhase.COMPLETED if cycle.completed else AutonomousExecutionPhase.STOPPED,
            replanning=cycle,
            preflight_reasons=tuple(preflight_reasons),
        )


__all__ = ["AutonomousTradingControlResult", "AutonomousTradingController"]
