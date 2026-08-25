from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.domain.execution import ExecutionRequest, ExecutionResult, ExecutionStatus
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_request_factory_v06 import build_execution_request


@dataclass(frozen=True, slots=True)
class ExecutionIntakeResult:
    request: ExecutionRequest
    result: ExecutionResult
    accepted: bool = True
    reason: str = ""


class ExecutionIntakeService:
    """0.6.6 boundary between validated opportunity results and Execution Center."""

    def __init__(
        self,
        confirmation_service: ControlledExecutionService,
        *,
        request_factory=build_execution_request,
    ) -> None:
        self.confirmation_service = confirmation_service
        self.request_factory = request_factory

    def intake(self, *, account_id: str, result: Any) -> ExecutionIntakeResult:
        request = self.request_factory(account_id=account_id, result=result)
        prepared = self.confirmation_service.prepare(request)
        return ExecutionIntakeResult(
            request=request,
            result=prepared,
            accepted=prepared.status is not ExecutionStatus.BLOCKED,
            reason=prepared.error_message or "",
        )

    def enqueue(self, *, account_id: str, result: Any) -> ExecutionIntakeResult:
        return self.intake(account_id=account_id, result=result)

    def prepare(self, *, account_id: str, result: Any) -> ExecutionIntakeResult:
        return self.intake(account_id=account_id, result=result)

    def request_confirmation(self, request: ExecutionRequest) -> ExecutionResult:
        return self.confirmation_service.request_confirmation(request)

    def cancel(self, request: ExecutionRequest) -> ExecutionResult:
        return self.confirmation_service.cancel_before_submission(request)


__all__ = ["ExecutionIntakeResult", "ExecutionIntakeService"]
