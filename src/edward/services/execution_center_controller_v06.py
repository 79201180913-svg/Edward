from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from edward.domain.execution import ExecutionEvent, ExecutionRequest, ExecutionResult, ExecutionStatus
from edward.services.execution_bridge_service_v06 import ExecutionQueueItem
from edward.services.execution_confirmation_service import ControlledExecutionService


@dataclass(frozen=True, slots=True)
class ExecutionCenterState:
    request: ExecutionRequest | None = None
    result: ExecutionResult | None = None
    status: ExecutionStatus | None = None
    events: tuple[ExecutionEvent, ...] = ()


class ExecutionCenterController:
    """UI-facing coordinator for the controlled execution flow."""

    def __init__(self, service: ControlledExecutionService, on_change: Callable[[ExecutionCenterState], None] | None = None) -> None:
        self.service = service
        self.on_change = on_change
        self.state = ExecutionCenterState()

    def load_request(self, request: ExecutionRequest) -> ExecutionCenterState:
        if self.state.request is not None and self.state.request.execution_id != request.execution_id:
            raise ValueError("another execution is already active")
        self.state = ExecutionCenterState(request=request, status=ExecutionStatus.CREATED)
        self._publish()
        return self.state

    def load_queue_item(self, item: ExecutionQueueItem) -> ExecutionCenterState:
        """Load an already-queued execution without resetting its current status."""
        self.state = ExecutionCenterState(
            request=item.request,
            result=item.result,
            status=item.result.status,
            events=self.state.events,
        )
        self._publish()
        return self.state

    def prepare(self) -> ExecutionResult:
        request = self._require_request()
        result = self.service.prepare(request)
        self._set_result(result)
        return result

    def request_confirmation(self) -> ExecutionResult:
        request = self._require_request()
        result = self.service.request_confirmation(request)
        self._set_result(result)
        return result

    def confirm_and_submit(self) -> ExecutionResult:
        request = self._require_request()
        result = self.service.confirm_and_submit(request)
        self._set_result(result)
        return result

    def cancel(self) -> ExecutionResult:
        request = self._require_request()
        result = self.service.cancel_before_submission(request)
        self._set_result(result)
        return result

    def accept_event(self, event: ExecutionEvent) -> None:
        self.state = ExecutionCenterState(
            request=self.state.request,
            result=self.state.result,
            status=event.status,
            events=self.state.events + (event,),
        )
        self._publish()

    def _set_result(self, result: ExecutionResult) -> None:
        self.state = ExecutionCenterState(
            request=self.state.request,
            result=result,
            status=result.status,
            events=self.state.events,
        )
        self._publish()

    def _require_request(self) -> ExecutionRequest:
        if self.state.request is None:
            raise RuntimeError("execution request is not loaded")
        return self.state.request

    def _publish(self) -> None:
        callback = self.on_change
        if callback is None:
            return
        try:
            callback(self.state)
        except Exception:
            # UI callbacks may outlive their Tk widgets after a window is closed.
            # Detach a stale callback so later state publications do not break
            # the execution flow.
            self.on_change = None
