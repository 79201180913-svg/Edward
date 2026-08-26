from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.services.autonomous_planning_service import AutonomousPlanningResult, AutonomousPlanningService
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


class AutonomousCycleService:
    """Coordinate one read-only autonomous cycle including allocation planning.

    Market analysis remains the responsibility of OpportunitySearchService.
    This layer adds live capital planning, portfolio/market comparison and a
    slot-aware reallocation plan. No orders are sent here.
    """

    def __init__(
        self,
        planning_service: AutonomousPlanningService,
        opportunity_service: OpportunitySearchService,
        reallocation_service: PortfolioReallocationService | None = None,
    ) -> None:
        self._planning = planning_service
        self._opportunities = opportunity_service
        self._reallocation = reallocation_service or PortfolioReallocationService()

    def run(
        self,
        *,
        account_id: str,
        policy: BudgetPlanningPolicy,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
        progress_callback: Callable[[str, float, int, int], None] | None = None,
        result_callback: Callable[[OpportunitySearchResult, int, int], None] | None = None,
        scope_callback: Callable[[str], None] | None = None,
        planning_callback: Callable[[AutonomousPlanningResult], None] | None = None,
    ) -> AutonomousCycleResult:
        planning = self._planning.plan(account_id, policy)
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
        if progress_callback is not None:
            try:
                progress_callback("План перераспределения готов", 100.0, len(allocation), len(allocation))
            except Exception:
                pass

        return AutonomousCycleResult(
            planning=planning,
            market_opportunities=tuple(market),
            portfolio_opportunities=tuple(portfolio),
            allocation_actions=allocation,
        )
