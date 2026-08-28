from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from edward.domain.execution import ExecutionRequest, ExecutionResult, ExecutionStatus
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_intake_service_v06 import ExecutionIntakeResult, ExecutionIntakeService
from edward.services.execution_request_factory_v06 import build_execution_request

_TERMINAL_STATUSES = {
    ExecutionStatus.CANCELLED, ExecutionStatus.BLOCKED, ExecutionStatus.FAILED,
    ExecutionStatus.REJECTED, ExecutionStatus.FILLED, ExecutionStatus.RECONCILED,
    ExecutionStatus.TIMEOUT,
}


@dataclass(frozen=True, slots=True)
class ExecutionQueueItem:
    request: ExecutionRequest
    result: ExecutionResult


class ExecutionBridgeService:
    """Bridge from opportunity results to the Execution Center queue."""

    def __init__(self, confirmation_service: ControlledExecutionService) -> None:
        self.intake = ExecutionIntakeService(confirmation_service)
        self._items: dict[str, ExecutionQueueItem] = {}

    def enqueue_opportunity(self, *, account_id: str, result: Any) -> ExecutionIntakeResult:
        if bool(getattr(result, "execution_ready", False)):
            request = build_execution_request(account_id=account_id, result=result)
            existing = self._items.get(request.execution_id)
            if existing is not None and existing.result.status not in _TERMINAL_STATUSES:
                return ExecutionIntakeResult(request=existing.request, result=existing.result, accepted=False, reason="Заявка уже передана в исполнение")
        accepted = self.intake.enqueue(account_id=account_id, result=result)
        if not accepted.accepted:
            return accepted
        self._items[accepted.request.execution_id] = ExecutionQueueItem(accepted.request, accepted.result)
        return accepted

    def has_active_opportunity(self, *, account_id: str, result: Any) -> bool:
        if not bool(getattr(result, "execution_ready", False)):
            return False
        request = build_execution_request(account_id=account_id, result=result)
        item = self._items.get(request.execution_id)
        return item is not None and item.result.status not in _TERMINAL_STATUSES

    def get(self, execution_id: str) -> ExecutionQueueItem | None:
        return self._items.get(execution_id)

    def all(self) -> tuple[ExecutionQueueItem, ...]:
        return tuple(self._items.values())

    def request_confirmation(self, execution_id: str) -> ExecutionResult:
        item = self._require(execution_id)
        result = self.intake.request_confirmation(item.request)
        self._items[execution_id] = ExecutionQueueItem(item.request, result)
        return result

    def autonomous_submit(self, execution_id: str) -> ExecutionResult:
        item = self._require(execution_id)
        result = self.intake.confirmation_service.autonomous_submit(item.request)
        self._items[execution_id] = ExecutionQueueItem(item.request, result)
        return result

    def monitor(self, execution_id: str) -> ExecutionResult:
        item = self._require(execution_id)
        result = self.intake.confirmation_service.engine.monitor(execution_id)
        self._items[execution_id] = ExecutionQueueItem(item.request, result)
        return result

    def wait_for_terminal(self, execution_id: str, *, timeout_seconds: float = 30.0, poll_interval_seconds: float = 1.0) -> ExecutionResult:
        """Poll broker status until the order reaches a terminal state.

        Autonomous verification must not treat SUBMITTED as a filled trade.
        When the order does not reach a terminal state before the timeout, the
        bridge cancels it and returns the resulting terminal status.
        """
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")

        item = self._require(execution_id)
        current = item.result
        if current.status in _TERMINAL_STATUSES:
            return current

        deadline = time.monotonic() + timeout_seconds
        while True:
            current = self.monitor(execution_id)
            if current.status in _TERMINAL_STATUSES:
                return current
            if time.monotonic() >= deadline:
                cancelled = self.cancel(execution_id)
                return cancelled
            time.sleep(min(poll_interval_seconds, max(0.0, deadline - time.monotonic())))

    def cancel(self, execution_id: str) -> ExecutionResult:
        item = self._require(execution_id)
        result = self.intake.cancel(item.request)
        self._items[execution_id] = ExecutionQueueItem(item.request, result)
        return result

    def remove_terminal(self, execution_id: str) -> bool:
        item = self._items.get(execution_id)
        if item is None:
            return False
        if item.result.status in _TERMINAL_STATUSES:
            del self._items[execution_id]
            return True
        return False

    def _require(self, execution_id: str) -> ExecutionQueueItem:
        item = self._items.get(execution_id)
        if item is None:
            raise KeyError(execution_id)
        return item


__all__ = ["ExecutionBridgeService", "ExecutionQueueItem"]
