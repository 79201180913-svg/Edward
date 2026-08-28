from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from edward.domain.execution import ExecutionRequest, ExecutionResult, ExecutionStatus, ExecutionMode
from edward.services.execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)


class PreTradeValidator(Protocol):
    def validate(self, request: ExecutionRequest) -> tuple[bool, tuple[str, ...]]: ...


@dataclass(frozen=True, slots=True)
class PreTradeValidationResult:
    passed: bool
    reasons: tuple[str, ...] = ()


class ControlledExecutionService:
    """Coordinator for user-confirmed and explicitly authorized autonomous execution."""

    def __init__(self, engine: ExecutionEngine, validator: PreTradeValidator) -> None:
        self.engine = engine
        self.validator = validator

    def prepare(self, request: ExecutionRequest) -> ExecutionResult:
        created = self.engine.create(request)
        if created.status != ExecutionStatus.CREATED:
            return created
        return self.engine.validate(request)

    def request_confirmation(self, request: ExecutionRequest) -> ExecutionResult:
        current = self._status(request.execution_id)
        if current != ExecutionStatus.READY:
            raise ValueError(f"confirmation is not available from {current}")
        logger.info("[EXECUTION] WAITING_CONFIRMATION execution_id=%s", request.execution_id)
        return self.engine.require_confirmation(request)

    def confirm_and_submit(self, request: ExecutionRequest) -> ExecutionResult:
        current = self._status(request.execution_id)
        if current != ExecutionStatus.WAITING_CONFIRMATION:
            raise ValueError(f"submission is not available from {current}")
        passed, reasons = self.validator.validate(request)
        if not passed:
            return self._blocked(request, reasons)
        self.engine.confirm(request)
        return self.engine.submit(request, mode=ExecutionMode.USER_CONFIRMATION)

    def autonomous_submit(self, request: ExecutionRequest) -> ExecutionResult:
        """Submit only from READY after the autonomous controller has authorized the step."""
        current = self._status(request.execution_id)
        if current != ExecutionStatus.READY:
            raise ValueError(f"autonomous submission is not available from {current}")
        passed, reasons = self.validator.validate(request)
        if not passed:
            return self._blocked(request, reasons)
        logger.info("[EXECUTION] AUTONOMOUS AUTHORIZED execution_id=%s ticker=%s", request.execution_id, request.ticker)
        return self.engine.submit(request, mode=ExecutionMode.AUTONOMOUS)

    def cancel_before_submission(self, request: ExecutionRequest) -> ExecutionResult:
        current = self._status(request.execution_id)
        if current != ExecutionStatus.WAITING_CONFIRMATION:
            raise ValueError(f"cancellation is not available from {current}")
        self.engine._update_status(request.execution_id, ExecutionStatus.CANCELLED)
        return ExecutionResult(request.execution_id, ExecutionStatus.CANCELLED)

    def _blocked(self, request: ExecutionRequest, reasons: tuple[str, ...]) -> ExecutionResult:
        logger.warning("[EXECUTION] PRETRADE BLOCKED execution_id=%s reasons=%s", request.execution_id, list(reasons))
        entry = self.engine.journal.get(request.execution_id)
        if entry is not None:
            self.engine._update_status(request.execution_id, ExecutionStatus.BLOCKED, error_code="PRETRADE_VALIDATION_FAILED", error_message=";".join(reasons))
        return ExecutionResult(request.execution_id, ExecutionStatus.BLOCKED, error_code="PRETRADE_VALIDATION_FAILED", error_message=";".join(reasons))

    def _status(self, execution_id: str) -> ExecutionStatus:
        entry = self.engine.journal.get(execution_id)
        if entry is None:
            raise KeyError(execution_id)
        return entry.status
