from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from edward.services.autonomous_execution_plan_service import ExecutionPlanStep
from edward.services.account_state_refresh_service import AccountState


@dataclass(frozen=True, slots=True)
class ExecutionVerification:
    passed: bool
    actual_quantity: int
    expected_quantity: int
    reasons: tuple[str, ...] = ()


class AutonomousExecutionVerificationService:
    """Verify an executed autonomous step against refreshed live account state."""

    def verify(
        self,
        *,
        step: ExecutionPlanStep,
        state: AccountState,
        expected_quantity: int,
        before_quantity: int = 0,
    ) -> ExecutionVerification:
        actual = self._quantity(state.positions, step.instrument_uid)
        reasons: list[str] = []
        action = step.action.upper()

        if action in {"BUY", "ADD"}:
            if actual < expected_quantity:
                reasons.append(f"POSITION_QUANTITY_NOT_REACHED:{actual}<{expected_quantity}")
        elif action == "SELL":
            if actual != 0:
                reasons.append(f"POSITION_NOT_CLOSED:{actual}")
        elif action == "REDUCE":
            if actual >= before_quantity:
                reasons.append(f"POSITION_NOT_REDUCED:{actual}>={before_quantity}")
        else:
            reasons.append(f"UNSUPPORTED_VERIFICATION_ACTION:{action}")

        return ExecutionVerification(
            passed=not reasons,
            actual_quantity=actual,
            expected_quantity=expected_quantity,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _quantity(positions: Iterable[Any], instrument_uid: str) -> int:
        for position in positions or ():
            uid = getattr(position, "instrument_uid", None)
            if isinstance(position, dict):
                uid = position.get("instrument_uid", position.get("uid"))
            if str(uid or "") != instrument_uid:
                continue
            value = getattr(position, "quantity", None)
            if isinstance(position, dict):
                value = position.get("quantity", position.get("quantity_lots", 0))
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        return 0


__all__ = ["AutonomousExecutionVerificationService", "ExecutionVerification"]
