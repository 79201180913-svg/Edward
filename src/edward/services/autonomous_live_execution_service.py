from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState, AccountStateRefreshService
from edward.services.autonomous_cycle_service import AutonomousCycleService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_planning_service import AutonomousPlanningService
from edward.services.autonomous_trading_controller import AutonomousTradingControlResult, AutonomousTradingController
from edward.services.budget_planning_service import BudgetPlan, BudgetPlanningPolicy
from edward.services.opportunity_search_service import MARKET_SCOPE, PORTFOLIO_SCOPE, OpportunitySearchResult, OpportunitySearchService
from edward.services.portfolio_reallocation_service import PortfolioReallocationService


@dataclass(frozen=True, slots=True)
class AutonomousLiveExecutionResult:
    control: AutonomousTradingControlResult
    plans_built: int
    opportunities_scanned: int


class AutonomousLiveExecutionService:
    """Connect the existing analysis/planning services to the controlled live cycle.

    No market-data implementation lives here. OpportunitySearchService remains
    the source of analysis results; planning/reallocation remain the source of
    capital decisions; the controller remains the only execution gate.
    """

    def __init__(
        self,
        *,
        account_state: AccountStateRefreshService,
        planning: AutonomousPlanningService,
        opportunities: OpportunitySearchService,
        reallocation: PortfolioReallocationService,
        execution_controller: AutonomousTradingController,
        execution_plan_builder: Any,
        client: Any,
    ) -> None:
        self._state = account_state
        self._planning = planning
        self._opportunities = opportunities
        self._reallocation = reallocation
        self._controller = execution_controller
        self._execution_plan_builder = execution_plan_builder
        self._client = client

    def run(
        self,
        *,
        account_id: str,
        policy: BudgetPlanningPolicy,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
        mode: ExecutionMode = ExecutionMode.ANALYSIS_ONLY,
        result_factory: Callable[[Any], Any] | None = None,
        progress_callback: Callable[[str, float, int, int], None] | None = None,
    ) -> AutonomousLiveExecutionResult:
        plan_count = 0
        scanned = 0
        budget_cache: dict[int, BudgetPlan] = {}
        result_cache: dict[str, OpportunitySearchResult] = {}

        def refresh() -> AccountState:
            return self._state.refresh(account_id)

        def build_plan(state: AccountState) -> AutonomousExecutionPlan:
            nonlocal plan_count, scanned
            planning = self._planning.plan(account_id, policy)
            budget_cache[id(state)] = planning.budget

            market = self._opportunities.scan(
                profile=profile,
                instrument_kind=instrument_kind,
                scope=MARKET_SCOPE,
                progress_callback=progress_callback,
                force_recompute=True,
            )
            portfolio = self._opportunities.scan(
                profile=profile,
                instrument_kind=instrument_kind,
                scope=PORTFOLIO_SCOPE,
                progress_callback=progress_callback,
                force_recompute=True,
            )
            scanned += len(market) + len(portfolio)
            for item in (*market, *portfolio):
                result_cache[item.instrument_uid] = item

            allocation = self._reallocation.plan(
                budget=planning.budget,
                market_opportunities=market,
                portfolio_opportunities=portfolio,
            )
            plan = self._execution_plan_builder.build(allocation)
            plan_count += 1
            return plan

        def budget_for_state(state: AccountState) -> BudgetPlan:
            cached = budget_cache.get(id(state))
            if cached is not None:
                return cached
            budget = self._planning.plan(account_id, policy).budget
            budget_cache[id(state)] = budget
            return budget

        def fresh_result(step: Any) -> Any:
            if result_factory is not None:
                return result_factory(step)

            scope = PORTFOLIO_SCOPE if str(step.action).upper() in {"SELL", "REDUCE"} else MARKET_SCOPE
            results = self._opportunities.scan(
                profile=profile,
                instrument_kind=instrument_kind,
                scope=scope,
                progress_callback=progress_callback,
                force_recompute=True,
            )
            scanned += len(results)
            for item in results:
                result_cache[item.instrument_uid] = item
            for item in results:
                if item.instrument_uid == step.instrument_uid and str(item.ticker) == str(step.ticker):
                    return item
            raise ValueError(f"FRESH_OPPORTUNITY_NOT_FOUND:{step.instrument_uid}:{step.ticker}")

        control = self._controller.execute_replanned(
            account_id=account_id,
            mode=mode,
            refresh_state=refresh,
            build_plan=build_plan,
            budget_for_state=budget_for_state,
            result_factory=fresh_result,
        )
        return AutonomousLiveExecutionResult(
            control=control,
            plans_built=plan_count,
            opportunities_scanned=scanned,
        )


__all__ = ["AutonomousLiveExecutionResult", "AutonomousLiveExecutionService"]
