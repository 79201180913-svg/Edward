from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from edward.domain.execution import ExecutionMode, ExecutionStatus
from edward.services.account_state_refresh_service import AccountState, AccountStateRefreshService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_service import AutonomousExecutionService
from edward.services.autonomous_execution_verification_service import AutonomousExecutionVerificationService, ExecutionVerification
from edward.services.execution_bridge_service_v06 import ExecutionBridgeService


class AutonomousExecutionPhase(StrEnum):
    PREPARING = "PREPARING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"


@dataclass(frozen=True, slots=True)
class AutonomousExecutionPhaseEvent:
    sequence: int | None
    phase: AutonomousExecutionPhase
    message: str = ""


@dataclass(frozen=True, slots=True)
class AutonomousExecutionStepResult:
    step: ExecutionPlanStep
    execution_id: str | None
    status: ExecutionStatus | None
    verification: ExecutionVerification | None
    completed: bool
    phase: AutonomousExecutionPhase = AutonomousExecutionPhase.STOPPED
    reason: str = ""


@dataclass(frozen=True, slots=True)
class AutonomousExecutionSequenceResult:
    steps: tuple[AutonomousExecutionStepResult, ...]
    completed: bool
    stopped_at: int | None = None
    phase: AutonomousExecutionPhase = AutonomousExecutionPhase.STOPPED
    events: tuple[AutonomousExecutionPhaseEvent, ...] = ()


class AutonomousExecutionSequenceService:
    """Execute approved autonomous steps strictly one-by-one."""

    def __init__(self, bridge: ExecutionBridgeService, state_refresh: AccountStateRefreshService, *, step_service: AutonomousExecutionService | None = None, verifier: AutonomousExecutionVerificationService | None = None) -> None:
        self._bridge = bridge
        self._refresh = state_refresh
        self._steps = step_service or AutonomousExecutionService(bridge)
        self._verifier = verifier or AutonomousExecutionVerificationService()

    def execute_confirmed_plan(self, *, account_id: str, plan: AutonomousExecutionPlan, result_factory: Callable[[ExecutionPlanStep], Any], mode: ExecutionMode = ExecutionMode.USER_CONFIRMATION) -> AutonomousExecutionSequenceResult:
        results: list[AutonomousExecutionStepResult] = []
        completed_sequences: set[int] = set()
        events: list[AutonomousExecutionPhaseEvent] = []

        def emit(sequence: int | None, phase: AutonomousExecutionPhase, message: str = "") -> None:
            events.append(AutonomousExecutionPhaseEvent(sequence, phase, message))

        for step in plan.steps:
            if step.depends_on is not None and step.depends_on not in completed_sequences:
                reason = f"DEPENDENCY_NOT_COMPLETED:{step.depends_on}"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, None, None, None, False, AutonomousExecutionPhase.STOPPED, reason))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence, AutonomousExecutionPhase.STOPPED, tuple(events))

            emit(step.sequence, AutonomousExecutionPhase.PREPARING, "Подготовка шага")
            before_state = self._refresh.refresh(account_id)
            before_quantity = self._quantity(before_state, step.instrument_uid)

            try:
                intake = self._steps.prepare_step_from_fresh_result(account_id=account_id, step=step, result_factory=result_factory, dependency_completed=True)
            except Exception as exc:
                reason = str(exc)
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, None, None, None, False, AutonomousExecutionPhase.STOPPED, reason))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence, AutonomousExecutionPhase.STOPPED, tuple(events))

            if not intake.accepted or intake.request is None:
                reason = intake.reason or "EXECUTION_INTAKE_REJECTED"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, getattr(intake.result, "execution_id", None), getattr(intake.result, "status", None), None, False, AutonomousExecutionPhase.STOPPED, reason))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence, AutonomousExecutionPhase.STOPPED, tuple(events))

            execution_id = intake.request.execution_id
            emit(step.sequence, AutonomousExecutionPhase.EXECUTING, f"Отправка {execution_id}")
            try:
                if mode is ExecutionMode.AUTONOMOUS:
                    submitted = self._bridge.autonomous_submit(execution_id)
                else:
                    waiting = self._bridge.request_confirmation(execution_id)
                    if waiting.status is not ExecutionStatus.WAITING_CONFIRMATION:
                        raise ValueError(f"CONFIRMATION_NOT_READY:{waiting.status}")
                    submitted = self._bridge.intake.confirmation_service.confirm_and_submit(intake.request)
            except Exception as exc:
                reason = str(exc)
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, execution_id, None, None, False, AutonomousExecutionPhase.STOPPED, reason))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence, AutonomousExecutionPhase.STOPPED, tuple(events))

            if submitted.status not in {ExecutionStatus.SUBMITTED, ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED, ExecutionStatus.RECONCILED}:
                reason = submitted.error_message or f"EXECUTION_STATUS:{submitted.status}"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, None, False, AutonomousExecutionPhase.STOPPED, reason))
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence, AutonomousExecutionPhase.STOPPED, tuple(events))

            emit(step.sequence, AutonomousExecutionPhase.VERIFYING, "Проверка результата")
            after_state = self._refresh.refresh(account_id)
            expected_quantity = int(submitted.filled_quantity)
            verification = self._verifier.verify(step=step, state=after_state, expected_quantity=expected_quantity, before_quantity=before_quantity)
            completed = verification.passed
            phase = AutonomousExecutionPhase.COMPLETED if completed else AutonomousExecutionPhase.STOPPED
            reason = "" if completed else ";".join(verification.reasons)
            emit(step.sequence, phase, reason or "Шаг выполнен")
            results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, verification, completed, phase, reason))
            if not completed:
                return AutonomousExecutionSequenceResult(tuple(results), False, step.sequence, AutonomousExecutionPhase.STOPPED, tuple(events))
            completed_sequences.add(step.sequence)

        emit(None, AutonomousExecutionPhase.COMPLETED, "План выполнен")
        return AutonomousExecutionSequenceResult(tuple(results), True, None, AutonomousExecutionPhase.COMPLETED, tuple(events))

    @staticmethod
    def _quantity(state: AccountState, instrument_uid: str) -> int:
        total = 0
        for position in state.positions or ():
            uid = getattr(position, "instrument_uid", None)
            value = getattr(position, "quantity", None)
            if isinstance(position, dict):
                uid = position.get("instrument_uid", position.get("uid"))
                value = position.get("quantity", position.get("quantity_lots", 0))
            if str(uid or "") != instrument_uid:
                continue
            try:
                total += int(value or 0)
            except (TypeError, ValueError):
                continue
        return total


__all__ = ["AutonomousExecutionPhase", "AutonomousExecutionPhaseEvent", "AutonomousExecutionSequenceService", "AutonomousExecutionSequenceResult", "AutonomousExecutionStepResult"]
