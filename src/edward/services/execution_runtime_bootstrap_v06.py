from __future__ import annotations

from typing import Any

from edward.services.execution_bridge_service_v06 import ExecutionBridgeService
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine
from edward.services.execution_queue_action_v06 import ExecutionQueueActionController
from edward.services.execution_center_controller_v06 import ExecutionCenterController
from edward.services.live_pretrade_validator_v06 import LivePreTradeValidator


def install_execution_runtime_bootstrap(app_class: type[Any]) -> None:
    if getattr(app_class, "_execution_runtime_bootstrap_v06_installed", False):
        return
    original_init = app_class.__init__

    def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        engine = ExecutionEngine(adapter=None)
        validator = LivePreTradeValidator(self.client)
        controlled = ControlledExecutionService(engine, validator)
        bridge = ExecutionBridgeService(controlled)
        controller = ExecutionCenterController(controlled)
        action = ExecutionQueueActionController(
            bridge=bridge,
            account_id_provider=lambda: self.context.require_account_id(),
        )
        self._execution_engine = engine
        self._execution_pretrade_validator = validator
        self._execution_confirmation_service = controlled
        self._execution_bridge = bridge
        self._execution_center_controller = controller
        self._execution_queue_action_controller = action

    app_class.__init__ = wrapped_init
    app_class._execution_runtime_bootstrap_v06_installed = True


__all__ = ["install_execution_runtime_bootstrap"]
