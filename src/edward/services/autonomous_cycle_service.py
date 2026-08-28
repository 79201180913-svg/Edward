from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.domain.execution import ExecutionMode
from edward.services.autonomous_execution_plan_service import (
    AutonomousExecutionPlan,
    AutonomousExecutionPlanService,
)
from edward.services.autonomous_planning_service import AutonomousPlanningResult, AutonomousPlanningService
from edward.services.autonomous_trading_controller import AutonomousTradingControlResult, AutonomousTradingController
from edward.services.budget_planning_service import BudgetPlanningPolicy
from edward.services.opportunity_search_service import (
    MARKET_SCOPE,
    PORTFOLIO_SCOPE,
    OpportunitySearchResult,
    OpportunitySearchService,
)
from edward.services.portfolio_reallocation_service import AllocationAction, PortfolioReallocationService


@dataclass(frozen=True, slots=True)
class AutonomousCycleResult:
    planning: AutonomousPlanningResult
    market_opportunities: tuple[OpportunitySearchResult, ...]
    portfolio_opportunities: tuple[OpportunitySearchResult, ...]
    allocation_actions: tuple[AllocationAction, ...] = ()
    execution_plan: AutonomousExecutionPlan | None = None


class AutonomousCycleService:
    """Coordinate analysis/planning and optionally hand execution to the controlled runtime."""

    def __init__(
        self,
        planning_service: AutonomousPlanningService,
        opportunity_service: OpportunitySearchService,
        reallocation_service: PortfolioReallocationService | None = None,
        execution_plan_service: AutonomousExecutionPlanService | None = None,
        trading_controller: AutonomousTradingController | None = None,
    ) -> None:
        self._planning = planning_service
        self._opportunities = opportunity_service
        self._reallocation = reallocation_service or PortfolioReallocationService()
        self._execution_plan = execution_plan_service or AutonomousExecutionPlanService()
        self._trading_controller = trading_controller

    def run(
        self,
        *,
        account_id: str,
        policy: BudgetPlanningPolicy,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
        account_state: Any | None = None,
        progress_callback: Callable[[str, float, int, int], None] | None = None,
        result_callback: Callable[[OpportunitySearchResult, int, int], None] | None = None,
        scope_callback: Callable[[str], None] | None = None,
        planning_callback: Callable[[AutonomousPlanningResult], None] | None = None,
    ) -> AutonomousCycleResult:
        if account_state is None:
            planning = self._planning.plan(account_id, policy)
        else:
            planning = self._planning.plan_from_state(
                account_id,
                policy,
                positions=account_state.positions,
                portfolio=account_state.portfolio,
            )
        if planning_callback is not None:
            planning_callback(planning)

        if scope_callback is not None:
            scope_callback(MARKET_SCOPE)
        market = self._opportunities.scan(
            profile=profile,
            instrument_kind=instrument_kind,
            scope=MARKET_SCOPE,
            progress_callback=progress_callback,
            result_callback=result_callback,
        )

        if scope_callback is not None:
            scope_callback(PORTFOLIO_SCOPE)
        portfolio = self._opportunities.scan(
            profile=profile,
            instrument_kind=instrument_kind,
            scope=PORTFOLIO_SCOPE,
            progress_callback=progress_callback,
            result_callback=result_callback,
        )

        if progress_callback is not None:
            try:
                progress_callback("Перераспределение портфеля", 98.0, 0, 0)
            except Exception:
                pass
        allocation = self._reallocation.plan(
            budget=planning.budget,
            market_opportunities=market,
            portfolio_opportunities=portfolio,
        )
        execution_plan = self._execution_plan.build(allocation)
        if progress_callback is not None:
            try:
                progress_callback("План исполнения подготовлен", 100.0, len(execution_plan.steps), len(execution_plan.steps))
            except Exception:
                pass

        return AutonomousCycleResult(
            planning=planning,
            market_opportunities=tuple(market),
            portfolio_opportunities=tuple(portfolio),
            allocation_actions=allocation,
            execution_plan=execution_plan,
        )

    def execute_replanned(
        self,
        *,
        account_id: str,
        mode: ExecutionMode,
        refresh_state: Callable[[], Any],
        build_plan: Callable[[Any], AutonomousExecutionPlan],
        budget_for_state: Callable[[Any], Any],
        result_factory: Callable[[Any], Any],
        max_iterations: int = 50,
        execution_event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> AutonomousTradingControlResult:
        """Run the live autonomous execution loop through the controlled controller."""
        if self._trading_controller is None:
            raise RuntimeError("AUTONOMOUS_TRADING_CONTROLLER_REQUIRED")
        return self._trading_controller.execute_replanned(
            account_id=account_id,
            mode=mode,
            refresh_state=refresh_state,
            build_plan=build_plan,
            budget_for_state=budget_for_state,
            result_factory=result_factory,
            max_iterations=max_iterations,
            execution_event_callback=execution_event_callback,
        )


__all__ = ["AutonomousCycleResult", "AutonomousCycleService"]
