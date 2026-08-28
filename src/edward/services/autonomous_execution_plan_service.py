from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from edward.services.portfolio_reallocation_service import (
    ADD, BUY, HOLD, REDUCE, REPLACE, SELL, AllocationAction,
)


@dataclass(frozen=True, slots=True)
class ExecutionPlanStep:
    sequence: int
    action: str
    ticker: str
    instrument_uid: str
    target_value: Decimal
    source_ticker: str | None = None
    source_instrument_uid: str | None = None
    depends_on: int | None = None
    requires_revalidation: bool = True
    execution_ready: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class AutonomousExecutionPlan:
    steps: tuple[ExecutionPlanStep, ...]
    executable: bool = False
    requires_user_confirmation: bool = True


class AutonomousExecutionPlanService:
    """Convert allocation decisions into an ordered, non-submitting execution plan."""

    _SELL_FIRST = {SELL, REDUCE}
    _BUY_AFTER = {BUY, ADD}

    def build(self, actions: Iterable[AllocationAction]) -> AutonomousExecutionPlan:
        actions = tuple(actions)
        steps: list[ExecutionPlanStep] = []
        replacement_buy_dependencies: list[tuple[AllocationAction, int]] = []

        # Phase 1: release every required slot/capital before any new BUY.
        for action in actions:
            if action.action in self._SELL_FIRST:
                steps.append(self._step(action, len(steps) + 1))
            elif action.action == REPLACE:
                sell = ExecutionPlanStep(
                    sequence=len(steps) + 1,
                    action=SELL,
                    ticker=action.source_ticker or "",
                    instrument_uid=action.source_instrument_uid or "",
                    target_value=action.target_value,
                    requires_revalidation=True,
                    execution_ready=False,
                    reason=f"Освободить слот перед заменой {action.ticker}. {action.reason}",
                )
                steps.append(sell)
                replacement_buy_dependencies.append((action, sell.sequence))

        # Phase 2: execute replacement BUYs and ordinary BUY/ADD operations.
        for action, sell_sequence in replacement_buy_dependencies:
            steps.append(
                ExecutionPlanStep(
                    sequence=len(steps) + 1,
                    action=BUY,
                    ticker=action.ticker,
                    instrument_uid=action.instrument_uid,
                    target_value=action.target_value,
                    source_ticker=action.source_ticker,
                    source_instrument_uid=action.source_instrument_uid,
                    depends_on=sell_sequence,
                    requires_revalidation=True,
                    execution_ready=False,
                    reason=f"Открыть новую позицию после продажи {action.source_ticker}. {action.reason}",
                )
            )
        for action in actions:
            if action.action in self._BUY_AFTER:
                steps.append(self._step(action, len(steps) + 1))

        return AutonomousExecutionPlan(steps=tuple(steps), executable=False, requires_user_confirmation=True)

    @staticmethod
    def _step(action: AllocationAction, sequence: int) -> ExecutionPlanStep:
        return ExecutionPlanStep(sequence=sequence, action=action.action, ticker=action.ticker, instrument_uid=action.instrument_uid, target_value=action.target_value, source_ticker=action.source_ticker, source_instrument_uid=action.source_instrument_uid, requires_revalidation=True, execution_ready=False, reason=action.reason)


__all__ = ["AutonomousExecutionPlan", "AutonomousExecutionPlanService", "ExecutionPlanStep"]
