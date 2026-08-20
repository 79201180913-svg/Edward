from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.account_state_refresh_service import AccountState, AccountStateRefreshService
from edward.services.execution_service import ExecutionContext, ExecutionService
from edward.services.order_monitor import OrderMonitor
from edward.services.order_submission_service import OrderSubmissionService
from edward.services.order_service import OrderRequest


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    order_id: str
    final_state: Any
    refreshed_state: AccountState


class TradingWorkflow:
    """End-to-end orchestration for a normal order in Sandbox/Production."""

    def __init__(
        self,
        submission: OrderSubmissionService,
        monitor: OrderMonitor,
        refresh: AccountStateRefreshService,
        execution: ExecutionService,
    ) -> None:
        self._submission = submission
        self._monitor = monitor
        self._refresh = refresh
        self._execution = execution

    def execute(
        self,
        request: OrderRequest,
        execution_context: ExecutionContext,
        interval_seconds: float = 1.0,
        timeout_seconds: float = 300.0,
    ) -> WorkflowResult:
        response = self._submission.submit(request)
        order_id = str(getattr(response, "order_id", None) or response.get("order_id"))
        if not order_id:
            raise RuntimeError("T-Invest did not return order_id")

        final_state = self._monitor.wait_for_terminal(
            request.account_id,
            order_id,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
        )
        self._execution.process(final_state, execution_context)
        refreshed_state = self._refresh.refresh(request.account_id)
        return WorkflowResult(order_id, final_state, refreshed_state)
