from __future__ import annotations

from typing import Any

from edward.services.execution_bridge_service_v06 import ExecutionBridgeService
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine
from edward.services.execution_queue_action_v06 import ExecutionQueueActionController
from edward.services.execution_center_controller_v06 import ExecutionCenterController
from edward.services.execution_opportunity_registry_v06 import install_live_scan_registry
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


class QueueOnlyPreTradeValidator:
    """0.6 UI bootstrap guard: queue works, broker submission remains blocked until live validator is wired."""

    def validate(self, request: Any) -> tuple[bool, tuple[str, ...]]:
        return False, ("LIVE_PRETRADE_VALIDATION_NOT_CONFIGURED",)


def install_execution_runtime_bootstrap(app_class: type[Any]) -> None:
    if getattr(app_class, "_execution_runtime_bootstrap_v06_installed", False):
        return
    install_live_scan_registry(LiveOpportunitySearchService)
    original_init = app_class.__init__

    def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        engine = ExecutionEngine(adapter=None)
        controlled = ControlledExecutionService(engine, QueueOnlyPreTradeValidator())
        bridge = ExecutionBridgeService(controlled)
        controller = ExecutionCenterController(controlled)
        action = ExecutionQueueActionController(
            bridge=bridge,
            account_id_provider=lambda: self.context.require_account_id(),
        )
        self._execution_engine = engine
        self._execution_confirmation_service = controlled
        self._execution_bridge = bridge
        self._execution_center_controller = controller
        self._execution_queue_action_controller = action

    app_class.__init__ = wrapped_init
    app_class._execution_runtime_bootstrap_v06_installed = True


__all__ = ["QueueOnlyPreTradeValidator", "install_execution_runtime_bootstrap"]
