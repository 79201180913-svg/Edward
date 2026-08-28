from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from edward.domain.execution import ExecutionMode, ExecutionStatus
from edward.services.account_state_refresh_service import AccountState, AccountStateRefreshService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_service import AutonomousExecutionService
from edward.services.autonomous_execution_verification_service import AutonomousExecutionVerificationService, ExecutionVerification
from edward.services.autonomous_protection_service import AutonomousProtectionService, ProtectionResult
from edward.services.execution_bridge_service_v06 import ExecutionBridgeService


class AutonomousExecutionPhase(StrEnum):
    PREPARING = "PREPARING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    PROTECTED = "PROTECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
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
    protection: ProtectionResult | None = None


@dataclass(frozen=True, slots=True)
class AutonomousExecutionSequenceResult:
    steps: tuple[AutonomousExecutionStepResult, ...]
    completed: bool
    stopped_at: int | None = None
    phase: AutonomousExecutionPhase = AutonomousExecutionPhase.STOPPED
    events: tuple[AutonomousExecutionPhaseEvent, ...] = ()

    @property
    def executed_steps(self) -> tuple[AutonomousExecutionStepResult, ...]:
        return tuple(step for step in self.steps if step.execution_id is not None)

    @property
    def failed_steps(self) -> tuple[AutonomousExecutionStepResult, ...]:
        return tuple(step for step in self.steps if not step.completed)


class AutonomousExecutionSequenceService:
    """Execute autonomous steps one-by-one, wait for broker completion and protect fills."""

    def __init__(
        self,
        bridge: ExecutionBridgeService,
        state_refresh: AccountStateRefreshService,
        *,
        step_service: AutonomousExecutionService | None = None,
        verifier: AutonomousExecutionVerificationService | None = None,
        protection_service: AutonomousProtectionService | None = None,
        execution_timeout_seconds: float = 30.0,
        execution_poll_interval_seconds: float = 1.0,
    ) -> None:
        if execution_timeout_seconds < 0:
            raise ValueError("execution_timeout_seconds must be non-negative")
        if execution_poll_interval_seconds <= 0:
            raise ValueError("execution_poll_interval_seconds must be positive")
        self._bridge = bridge
        self._refresh = state_refresh
        self._steps = step_service or AutonomousExecutionService(bridge)
        self._verifier = verifier or AutonomousExecutionVerificationService()
        self._protection = protection_service
        self._execution_timeout_seconds = execution_timeout_seconds
        self._execution_poll_interval_seconds = execution_poll_interval_seconds

    def execute_confirmed_plan(
        self,
        *,
        account_id: str,
        plan: AutonomousExecutionPlan,
        result_factory: Callable[[ExecutionPlanStep], Any],
        mode: ExecutionMode = ExecutionMode.USER_CONFIRMATION,
    ) -> AutonomousExecutionSequenceResult:
        results: list[AutonomousExecutionStepResult] = []
        completed_sequences: set[int] = set()
        events: list[AutonomousExecutionPhaseEvent] = []
        cycle_failed = False
        first_failure: int | None = None
        continued_after_failure = False

        def emit(sequence: int | None, phase: AutonomousExecutionPhase, message: str = "") -> None:
            events.append(AutonomousExecutionPhaseEvent(sequence, phase, message))

        for step in plan.steps:
            if step.depends_on is not None and step.depends_on not in completed_sequences:
                reason = f"DEPENDENCY_NOT_COMPLETED:{step.depends_on}"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, None, None, None, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                has_later_independent = any(
                    later.sequence > step.sequence and later.depends_on is None
                    for later in plan.steps
                )
                if not has_later_independent:
                    break
                continue

            emit(step.sequence, AutonomousExecutionPhase.PREPARING, "Подготовка шага")
            try:
                before_state = self._refresh.refresh(account_id)
                before_quantity = self._quantity(before_state, step.instrument_uid)
            except Exception as exc:
                reason = f"STATE_REFRESH_FAILED:{exc}"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, None, None, None, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                continue

            try:
                result = result_factory(step)
                intake = self._steps.prepare_step(account_id=account_id, step=step, result=result, dependency_completed=True)
            except Exception as exc:
                reason = str(exc)
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, None, None, None, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                continue

            if not intake.accepted or intake.request is None:
                reason = intake.reason or "EXECUTION_INTAKE_REJECTED"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, getattr(intake.result, "execution_id", None), getattr(intake.result, "status", None), None, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                continue

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

                if submitted.status not in {ExecutionStatus.SUBMITTED, ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED, ExecutionStatus.RECONCILED}:
                    raise RuntimeError(submitted.error_message or f"EXECUTION_STATUS:{submitted.status}")

                if submitted.status in {ExecutionStatus.SUBMITTED, ExecutionStatus.PARTIALLY_FILLED}:
                    emit(step.sequence, AutonomousExecutionPhase.EXECUTING, "Ожидание исполнения брокером")
                    submitted = self._bridge.wait_for_terminal(
                        execution_id,
                        timeout_seconds=self._execution_timeout_seconds,
                        poll_interval_seconds=self._execution_poll_interval_seconds,
                    )
            except Exception as exc:
                reason = str(exc)
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, execution_id, None, None, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                continue

            if submitted.status not in {ExecutionStatus.FILLED, ExecutionStatus.RECONCILED}:
                reason = submitted.error_message or f"EXECUTION_STATUS:{submitted.status}"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, None, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                continue

            emit(step.sequence, AutonomousExecutionPhase.VERIFYING, "Проверка результата")
            try:
                after_state = self._refresh.refresh(account_id)
                expected_quantity = int(submitted.filled_quantity)
                verification = self._verifier.verify(step=step, state=after_state, expected_quantity=expected_quantity, before_quantity=before_quantity)
            except Exception as exc:
                reason = f"VERIFICATION_FAILED:{exc}"
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, None, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                continue

            if not verification.passed:
                reason = ";".join(verification.reasons)
                emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, verification, False, AutonomousExecutionPhase.STOPPED, reason))
                cycle_failed = True
                if first_failure is None:
                    first_failure = step.sequence
                continue

            protection = None
            if self._protection is not None and step.action in {"BUY", "ADD"}:
                emit(step.sequence, AutonomousExecutionPhase.PROTECTED, "Создание защитного Stop Loss")
                try:
                    protection = self._protection.protect_fill(account_id=account_id, instrument_uid=step.instrument_uid, quantity=expected_quantity, result=result)
                except Exception as exc:
                    reason = f"PROTECTION_FAILED:{exc}"
                    emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                    results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, verification, False, AutonomousExecutionPhase.STOPPED, reason))
                    cycle_failed = True
                    if first_failure is None:
                        first_failure = step.sequence
                    continue
                if not protection.protected:
                    reason = protection.reason or "PROTECTION_FAILED"
                    emit(step.sequence, AutonomousExecutionPhase.STOPPED, reason)
                    results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, verification, False, AutonomousExecutionPhase.STOPPED, reason, protection))
                    cycle_failed = True
                    if first_failure is None:
                        first_failure = step.sequence
                    continue

            emit(step.sequence, AutonomousExecutionPhase.COMPLETED, "Шаг выполнен и защищён" if protection is not None else "Шаг выполнен")
            results.append(AutonomousExecutionStepResult(step, execution_id, submitted.status, verification, True, AutonomousExecutionPhase.COMPLETED, "", protection))
            if first_failure is not None and step.sequence != first_failure:
                continued_after_failure = True
            completed_sequences.add(step.sequence)

        if not cycle_failed:
            final_phase = AutonomousExecutionPhase.COMPLETED
            emit(None, final_phase, "План выполнен")
        elif continued_after_failure:
            final_phase = AutonomousExecutionPhase.FAILED
            emit(None, final_phase, "План завершён с ошибками")
        else:
            final_phase = AutonomousExecutionPhase.STOPPED

        return AutonomousExecutionSequenceResult(tuple(results), not cycle_failed, first_failure, final_phase, tuple(events))

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
