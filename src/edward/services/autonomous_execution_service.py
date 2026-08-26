from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.autonomous_execution_plan_service import ExecutionPlanStep
from edward.services.execution_bridge_service_v06 import ExecutionBridgeService
from edward.services.execution_intake_service_v06 import ExecutionIntakeResult


_EXECUTABLE_ACTIONS = {"BUY", "ADD", "REDUCE", "SELL"}


@dataclass(frozen=True, slots=True)
class AutonomousExecutionValidation:
    passed: bool
    reasons: tuple[str, ...] = ()


class AutonomousExecutionService:
    """Validate one autonomous plan step against a fresh opportunity result.

    This service does not submit orders itself. It validates that the current
    opportunity still matches the planned step and then delegates to the
    existing controlled Execution Bridge. Final live pre-trade validation and
    user confirmation therefore remain in the existing execution flow.
    """

    def __init__(self, bridge: ExecutionBridgeService) -> None:
        self.bridge = bridge

    def validate_step(
        self,
        *,
        step: ExecutionPlanStep,
        result: Any,
        dependency_completed: bool = True,
    ) -> AutonomousExecutionValidation:
        reasons: list[str] = []

        action = str(getattr(result, "decision", "") or "").upper()
        if step.action not in _EXECUTABLE_ACTIONS:
            reasons.append(f"UNSUPPORTED_PLAN_ACTION:{step.action}")
        if action != step.action:
            reasons.append(f"DECISION_MISMATCH:{action}!={step.action}")
        if not bool(getattr(result, "execution_ready", False)):
            reasons.append("EXECUTION_NOT_READY")

        instrument_uid = str(getattr(result, "instrument_uid", "") or "")
        if instrument_uid != step.instrument_uid:
            reasons.append(f"INSTRUMENT_UID_MISMATCH:{instrument_uid}!={step.instrument_uid}")

        ticker = str(getattr(result, "ticker", "") or "")
        if ticker != step.ticker:
            reasons.append(f"TICKER_MISMATCH:{ticker}!={step.ticker}")

        quantity = int(getattr(result, "recommended_quantity", 0) or 0)
        if quantity <= 0:
            reasons.append("INVALID_RECOMMENDED_QUANTITY")

        price = getattr(result, "price", None)
        if price is None:
            trade_plan = getattr(result, "trade_plan", None)
            price = getattr(trade_plan, "entry_price", None) if trade_plan is not None else None
        try:
            if price is None or float(price) <= 0:
                reasons.append("INVALID_ENTRY_PRICE")
        except (TypeError, ValueError):
            reasons.append("INVALID_ENTRY_PRICE")

        if step.depends_on is not None and not dependency_completed:
            reasons.append(f"DEPENDENCY_NOT_COMPLETED:{step.depends_on}")

        return AutonomousExecutionValidation(not reasons, tuple(reasons))

    def prepare_step(
        self,
        *,
        account_id: str,
        step: ExecutionPlanStep,
        result: Any,
        dependency_completed: bool = True,
    ) -> ExecutionIntakeResult:
        validation = self.validate_step(
            step=step,
            result=result,
            dependency_completed=dependency_completed,
        )
        if not validation.passed:
            raise ValueError("Autonomous execution step rejected: " + ";".join(validation.reasons))

        return self.bridge.enqueue_opportunity(account_id=account_id, result=result)


__all__ = ["AutonomousExecutionService", "AutonomousExecutionValidation"]
