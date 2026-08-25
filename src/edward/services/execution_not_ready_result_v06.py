from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.domain.execution import ExecutionRequest, ExecutionResult, ExecutionStatus


@dataclass(frozen=True, slots=True)
class ExecutionRejectedOpportunity:
    request: ExecutionRequest | None
    result: ExecutionResult
    accepted: bool = False
    reason: str = ""


def reject_not_ready_opportunity(*, result: Any) -> ExecutionRejectedOpportunity:
    execution_id = str(getattr(result, "instrument_uid", "") or "NOT_READY")
    reason = "execution_ready=False"
    return ExecutionRejectedOpportunity(
        request=None,
        result=ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.BLOCKED,
            error_code="EXECUTION_NOT_READY",
            error_message=reason,
        ),
        reason=reason,
    )
