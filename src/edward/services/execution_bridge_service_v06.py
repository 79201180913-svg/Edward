from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.domain.execution import ExecutionRequest, ExecutionResult, ExecutionStatus
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_intake_service_v06 import ExecutionIntakeResult, ExecutionIntakeService
from edward.services.execution_request_factory_v06 import build_execution_request


@dataclass(frozen=True, slots=True)
class ExecutionQueueItem:
    request: ExecutionRequest
    result: ExecutionResult


class ExecutionBridgeService:
    """0.6.7 bridge from opportunity results to the Execution Center queue."""

    def __init__(self, confirmation_service: ControlledExecutionService) -> None:
        self.intake = ExecutionIntakeService(confirmation_service)
        self._items: dict[str, ExecutionQueueItem] = {}

    def enqueue_opportunity(self, *, account_id: str, result: Any) -> ExecutionIntakeResult:
        request = build_execution_request(account_id=account_id, result=result)
        existing = self._items.get(request.execution_id)
        if existing is not None and existing.result.status not in {
            ExecutionStatus.CANCELLED,
            ExecutionStatus.BLOCKED,
            ExecutionStatus.FAILED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.FILLED,
            ExecutionStatus.RECONCILED,
            ExecutionStatus.TIMEOUT,
        }:
            return ExecutionIntakeResult(
                request=existing.request,
                result=existing.result,
                accepted=False,
                reason="Заявка уже передана в исполнение",
            )

        accepted = self.intake.enqueue(account_id=account_id, result=result)
        if not accepted.accepted:
            return accepted
        self._items[accepted.request.execution_id] = ExecutionQueueItem(
            request=accepted.request,
            result=accepted.result,
        )
        return accepted

    def has_active_opportunity(self, *, account_id: str, result: Any) -> bool:
        request = build_execution_request(account_id=account_id, result=result)
        item = self._items.get(request.execution_id)
        if item is None:
            return False
        return item.result.status not in {
            ExecutionStatus.CANCELLED,
            ExecutionStatus.BLOCKED,
            ExecutionStatus.FAILED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.FILLED,
            ExecutionStatus.RECONCILED,
            ExecutionStatus.TIMEOUT,
        }

    def get(self, execution_id: str) -> ExecutionQueueItem | None:
        return self._items.get(execution_id)

    def all(self) -> tuple[ExecutionQueueItem, ...]:
        return tuple(self._items.values())

    def request_confirmation(self, execution_id: str) -> ExecutionResult:
        item = self._require(execution_id)
        result = self.intake.request_confirmation(item.request)
        self._items[execution_id] = ExecutionQueueItem(item.request, result)
        return result

    def cancel(self, execution_id: str) -> ExecutionResult:
        item = self._require(execution_id)
        result = self.intake.cancel(item.request)
        self._items[execution_id] = ExecutionQueueItem(item.request, result)
        return result

    def remove_terminal(self, execution_id: str) -> bool:
        item = self._items.get(execution_id)
        if item is None:
            return False
        if item.result.status in {
            ExecutionStatus.CANCELLED,
            ExecutionStatus.BLOCKED,
            ExecutionStatus.FAILED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.FILLED,
            ExecutionStatus.RECONCILED,
            ExecutionStatus.TIMEOUT,
        }:
            del self._items[execution_id]
            return True
        return False

    def _require(self, execution_id: str) -> ExecutionQueueItem:
        item = self._items.get(execution_id)
        if item is None:
            raise KeyError(execution_id)
        return item


__all__ = ["ExecutionBridgeService", "ExecutionQueueItem"]
