from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edward.domain.execution import ExecutionRequest
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_request_factory_v06 import build_execution_request


@dataclass(frozen=True, slots=True)
class ExecutionIntakeResult:
    request: ExecutionRequest
    status: str


class ExecutionIntakeService:
    """Bridge validated opportunity results into the controlled execution queue."""

    def __init__(self, confirmation_service: ControlledExecutionService) -> None:
        self.confirmation_service = confirmation_service

    def intake(self, *, account_id: str, opportunity_result: Any) -> ExecutionIntakeResult:
        request = build_execution_request(account_id=account_id, result=opportunity_result)
        prepared = self.confirmation_service.prepare(request)
        return ExecutionIntakeResult(request=request, status=prepared.status.value)
