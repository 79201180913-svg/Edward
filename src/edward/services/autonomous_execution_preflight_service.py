from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.budget_planning_service import BudgetPlan


@dataclass(frozen=True, slots=True)
class ExecutionPreflightResult:
    passed: bool
    reasons: tuple[str, ...] = ()


class AutonomousExecutionPreflightService:
    """Validate an autonomous plan against freshly refreshed account state."""

    _BUY = {"BUY", "ADD"}
    _SELL = {"SELL", "REDUCE"}
    _ACTIVE_ORDER_STATUSES = {
        "NEW", "PENDING", "WAITING_CONFIRMATION", "EXECUTING",
        "SUBMITTED", "PARTIALLY_FILLED",
    }

    def validate(
        self,
        *,
        plan: AutonomousExecutionPlan,
        budget: BudgetPlan,
        state: AccountState,
    ) -> ExecutionPreflightResult:
        reasons: list[str] = []
        steps = tuple(plan.steps)
        if not steps:
            reasons.append("EMPTY_EXECUTION_PLAN")
            return ExecutionPreflightResult(False, tuple(reasons))

        self._validate_sequence(steps, reasons)
        positions = self._position_uids(state.positions)
        self._validate_positions(steps, positions, reasons)
        self._validate_conflicting_orders(steps, state.orders, reasons)
        self._validate_cash_and_slots(steps, budget, positions, reasons)
        return ExecutionPreflightResult(not reasons, tuple(reasons))

    @staticmethod
    def _validate_sequence(steps: tuple[Any, ...], reasons: list[str]) -> None:
        expected = list(range(1, len(steps) + 1))
        actual = [int(step.sequence) for step in steps]
        if actual != expected:
            reasons.append(f"INVALID_SEQUENCE:{actual}")

        known = set(actual)
        for step in steps:
            dependency = step.depends_on
            if dependency is None:
                continue
            if dependency not in known or dependency >= step.sequence:
                reasons.append(f"INVALID_DEPENDENCY:{step.sequence}->{dependency}")

    def _validate_positions(self, steps: tuple[Any, ...], positions: set[str], reasons: list[str]) -> None:
        simulated = set(positions)
        for step in steps:
            action = str(step.action).upper()
            uid = str(step.instrument_uid or "")
            if not uid:
                reasons.append(f"EMPTY_INSTRUMENT_UID:{step.sequence}")
                continue
            if action in self._SELL:
                if uid not in simulated:
                    reasons.append(f"POSITION_NOT_FOUND:{step.sequence}:{uid}")
                if action == "SELL":
                    simulated.discard(uid)
            elif action == "BUY":
                if uid in simulated:
                    reasons.append(f"BUY_ALREADY_HELD:{step.sequence}:{uid}")
                simulated.add(uid)
            elif action == "ADD":
                if uid not in simulated:
                    reasons.append(f"ADD_POSITION_NOT_FOUND:{step.sequence}:{uid}")
            elif action != "HOLD":
                reasons.append(f"UNSUPPORTED_PLAN_ACTION:{step.sequence}:{action}")

    def _validate_cash_and_slots(
        self,
        steps: tuple[Any, ...],
        budget: BudgetPlan,
        positions: set[str],
        reasons: list[str],
    ) -> None:
        buy_value = sum(
            (Decimal(str(step.target_value or 0)) for step in steps if str(step.action).upper() in self._BUY),
            Decimal("0"),
        )
        released_value = sum(
            (Decimal(str(step.target_value or 0)) for step in steps if str(step.action).upper() == "SELL"),
            Decimal("0"),
        )
        available = Decimal(str(budget.investable_cash)) + released_value
        if buy_value > available:
            reasons.append(f"INSUFFICIENT_INVESTABLE_CASH:{buy_value}>{available}")

        simulated = set(positions)
        for step in steps:
            action = str(step.action).upper()
            uid = str(step.instrument_uid or "")
            if action == "SELL":
                simulated.discard(uid)
            elif action == "BUY":
                simulated.add(uid)
        if len(simulated) > int(budget.slots):
            reasons.append(f"SLOT_LIMIT_EXCEEDED:{len(simulated)}>{budget.slots}")

    def _validate_conflicting_orders(self, steps: tuple[Any, ...], orders: Any, reasons: list[str]) -> None:
        active_uids: set[str] = set()
        for order in orders or ():
            status = self._field(order, "status", "")
            status = getattr(status, "value", str(status or "")).upper()
            if status not in self._ACTIVE_ORDER_STATUSES:
                continue
            uid = str(self._field(order, "instrument_uid", self._field(order, "uid", "")) or "")
            if uid:
                active_uids.add(uid)
        for step in steps:
            uid = str(step.instrument_uid or "")
            if uid in active_uids:
                reasons.append(f"ACTIVE_ORDER_CONFLICT:{step.sequence}:{uid}")

    @staticmethod
    def _position_uids(positions: Any) -> set[str]:
        result: set[str] = set()
        for position in positions or ():
            uid = AutonomousExecutionPreflightService._field(
                position, "instrument_uid", AutonomousExecutionPreflightService._field(position, "uid", "")
            )
            if uid:
                result.add(str(uid))
        return result

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)


__all__ = ["AutonomousExecutionPreflightService", "ExecutionPreflightResult"]
