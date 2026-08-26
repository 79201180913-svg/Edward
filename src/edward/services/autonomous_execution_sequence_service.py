from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.domain.execution import ExecutionStatus
from edward.services.account_state_refresh_service import AccountState, AccountStateRefreshService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_service import AutonomousExecutionService
from edward.services.autonomous_execution_verification_service import (
    AutonomousExecutionVerificationService,
    ExecutionVerification,
)
from edward.services.execution_bridge_service_v06 import ExecutionBridgeService


@dataclass(frozen=True, slots=True)
class AutonomousExecutionStepResult:
    step: ExecutionPlanStep
    execution_id: str | None
    status: ExecutionStatus | None
    verification: ExecutionVerification | None
    completed: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class AutonomousExecutionSequenceResult:
    steps: tuple[AutonomousExecutionStepResult, ...]
    completed: bool
    stopped_at: int | None = None


class AutonomousExecutionSequenceService:
    """Execute an already-approved plan strictly step-by-step.

    The service revalidates every step, uses the existing controlled execution
    flow, refreshes live account state after submission, and verifies the
    resulting position before allowing the next dependent step.
    """

    def __init__(
        self,
        bridge: ExecutionBridgeService,
        state_refresh: AccountStateRefreshService,
        *,
        step_service: AutonomousExecutionService | None = None,
        verifier: AutonomousExecutionVerificationService | None = None,
    ) -> None:
        self._bridge = bridge
        self._refresh = state_refresh
        self._steps = step_service or AutonomousExecutionService(bridge)
        self._verifier = verifier or AutonomousExecutionVerificationService()

    def execute_confirmed_plan(
        self,
        *,
        account_id: str,
        plan: AutonomousExecutionPlan,
        result_factory: Callable[[ExecutionPlanStep], Any],
    ) -> AutonomousExecutionSequenceResult:
        """Execute only after the caller has explicitly authorized the plan."""
        results: list[AutonomousExecutionStepResult] = []
        completed_sequences: set[int] = set()

        for step in plan.steps:
            if step.depends_on is not None and step.depends_on not in completed_sequences:
                item = AutonomousExecutionStepResult(
                    step=step,
                    execution_id=None,
                    status=None,
                    verification=None,
                    completed=False,
                    reason=f"DEPENDENCY_NOT_COMPLETED:{step.depends_on}",
                )
                results.append(item)
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence)

            before_state = self._refresh.refresh(account_id)
            before_quantity = self._quantity(before_state, step.instrument_uid)

            try:
                intake = self._steps.prepare_step_from_fresh_result(
                    account_id=account_id,
                    step=step,
                    result_factory=result_factory,
                    dependency_completed=True,
                )
            except Exception as exc:
                results.append(AutonomousExecutionStepResult(
                    step=step,
                    execution_id=None,
                    status=None,
                    verification=None,
                    completed=False,
                    reason=str(exc),
                ))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence)

            if not intake.accepted or intake.request is None:
                results.append(AutonomousExecutionStepResult(
                    step=step,
                    execution_id=getattr(intake.result, "execution_id", None),
                    status=getattr(intake.result, "status", None),
                    verification=None,
                    completed=False,
                    reason=intake.reason or "EXECUTION_INTAKE_REJECTED",
                ))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence)

            execution_id = intake.request.execution_id
            try:
                waiting = self._bridge.request_confirmation(execution_id)
                if waiting.status is not ExecutionStatus.WAITING_CONFIRMATION:
                    raise ValueError(f"CONFIRMATION_NOT_READY:{waiting.status}")
                submitted = self._bridge.intake.confirmation_service.confirm_and_submit(intake.request)
            except Exception as exc:
                results.append(AutonomousExecutionStepResult(
                    step=step,
                    execution_id=execution_id,
                    status=None,
                    verification=None,
                    completed=False,
                    reason=str(exc),
                ))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence)

            if submitted.status not in {ExecutionStatus.SUBMITTED, ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED, ExecutionStatus.RECONCILED}:
                results.append(AutonomousExecutionStepResult(
                    step=step,
                    execution_id=execution_id,
                    status=submitted.status,
                    verification=None,
                    completed=False,
                    reason=submitted.error_message or f"EXECUTION_STATUS:{submitted.status}",
                ))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence)

            after_state = self._refresh.refresh(account_id)
            expected_quantity = int(submitted.filled_quantity)
            verification = self._verifier.verify(
                step=step,
                state=after_state,
                expected_quantity=expected_quantity,
                before_quantity=before_quantity,
            )
            completed = verification.passed
            results.append(AutonomousExecutionStepResult(
                step=step,
                execution_id=execution_id,
                status=submitted.status,
                verification=verification,
                completed=completed,
                reason="" if completed else ";".join(verification.reasons),
            ))
            if not completed:
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence)
            completed_sequences.add(step.sequence)

        return AutonomousExecutionSequenceResult(tuple(results), True, None)

    @staticmethod
    def _quantity(state: AccountState, instrument_uid: str) -> int:
        total = 0
        for position in state.positions or ():
            uid = getattr(position, "instrument_uid", None)
            if isinstance(position, dict):
                uid = position.get("instrument_uid", position.get("uid"))
            if str(uid or "") != instrument_uid:
                continue
            value = getattr(position, "quantity", None)
            if isinstance(position, dict):
                value = position.get("quantity", position.get("quantity_lots", 0))
            try:
                total += int(value or 0)
            except (TypeError, ValueError):
                continue
        return total


__all__ = ["AutonomousExecutionSequenceService", "AutonomousExecutionSequenceResult", "AutonomousExecutionStepResult"]
