from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_execution_preflight_service import AutonomousExecutionPreflightService
from edward.services.autonomous_execution_sequence_service import (
    AutonomousExecutionSequenceResult,
    AutonomousExecutionSequenceService,
)
from edward.services.budget_planning_service import BudgetPlan


@dataclass(frozen=True, slots=True)
class AutonomousTradingControlResult:
    mode: ExecutionMode
    executed: bool
    reason: str
    sequence: AutonomousExecutionSequenceResult | None = None
    preflight_reasons: tuple[str, ...] = ()


class AutonomousTradingController:
    """Explicit gate between a generated autonomous plan and real submission."""

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
        if mode is not ExecutionMode.AUTONOMOUS:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="AUTONOMOUS_MODE_REQUIRED")
        if not self._enabled:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="AUTONOMOUS_TRADING_DISABLED")
        if not plan.steps:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="EMPTY_EXECUTION_PLAN")
        if budget is None or state is None:
            return AutonomousTradingControlResult(mode=mode, executed=False, reason="FRESH_ACCOUNT_STATE_REQUIRED")

        preflight = self._preflight.validate(plan=plan, budget=budget, state=state)
        if not preflight.passed:
            return AutonomousTradingControlResult(
                mode=mode,
                executed=False,
                reason="PREFLIGHT_REJECTED",
                preflight_reasons=preflight.reasons,
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
            sequence=sequence,
        )


__all__ = ["AutonomousTradingControlResult", "AutonomousTradingController"]
