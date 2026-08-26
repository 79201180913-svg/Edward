from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
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
    busy: bool = False
    error: str | None = None


Dispatch = Callable[[Callable[[ExecutionCenterState], None], ExecutionCenterState], None]


class ExecutionCenterController:
    """UI-facing coordinator for the controlled execution flow."""

    def __init__(
        self,
        service: ControlledExecutionService,
        on_change: Callable[[ExecutionCenterState], None] | None = None,
        dispatch: Dispatch | None = None,
    ) -> None:
        self.service = service
        self.on_change = on_change
        self.dispatch = dispatch or (lambda callback, state: callback(state))
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="edward-execution")
        self._closed = False
        self.state = ExecutionCenterState()

    def load_request(self, request: ExecutionRequest) -> ExecutionCenterState:
        if self.state.request is not None and self.state.request.execution_id != request.execution_id:
            raise ValueError("another execution is already active")
        self.state = ExecutionCenterState(request=request, status=ExecutionStatus.CREATED)
        self._publish()
        return self.state

    def load_queue_item(self, item: ExecutionQueueItem) -> ExecutionCenterState:
        """Load a queued execution without recursively reloading the current selection."""
        if self.state.request is not None and self.state.request.execution_id == item.request.execution_id:
            return self.state
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

    def confirm_and_submit_async(self) -> Future[ExecutionResult]:
        request = self._require_request()
        if self.state.busy:
            raise RuntimeError("execution operation is already running")
        self.state = ExecutionCenterState(
            request=request,
            result=self.state.result,
            status=self.state.status,
            events=self.state.events,
            busy=True,
            error=None,
        )
        self._publish()
        future = self._executor.submit(self.service.confirm_and_submit, request)
        future.add_done_callback(self._async_complete)
        return future

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
            busy=self.state.busy,
            error=self.state.error,
        )
        self._publish()

    def close(self) -> None:
        self._closed = True
        self.on_change = None
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _async_complete(self, future: Future[ExecutionResult]) -> None:
        try:
            result = future.result()
            next_state = ExecutionCenterState(
                request=self.state.request,
                result=result,
                status=result.status,
                events=self.state.events,
                busy=False,
                error=result.error_message,
            )
        except Exception as exc:
            next_state = ExecutionCenterState(
                request=self.state.request,
                result=self.state.result,
                status=ExecutionStatus.FAILED,
                events=self.state.events,
                busy=False,
                error=str(exc),
            )
        self.state = next_state
        self._publish()

    def _set_result(self, result: ExecutionResult) -> None:
        self.state = ExecutionCenterState(
            request=self.state.request,
            result=result,
            status=result.status,
            events=self.state.events,
            busy=False,
            error=result.error_message,
        )
        self._publish()

    def _require_request(self) -> ExecutionRequest:
        if self.state.request is None:
            raise RuntimeError("execution request is not loaded")
        return self.state.request

    def _publish(self) -> None:
        if self._closed:
            return
        callback = self.on_change
        if callback is None:
            return
        self.dispatch(callback, self.state)
