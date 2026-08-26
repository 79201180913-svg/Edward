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


@dataclass(frozen=True, slots=True)
class AutonomousCycleResult:
    planning: AutonomousPlanningResult
    market_opportunities: tuple[OpportunitySearchResult, ...]
    portfolio_opportunities: tuple[OpportunitySearchResult, ...]


class AutonomousCycleService:
    """Coordinate the existing v0.6 services for one read-only autonomous cycle.

    Market analysis remains the responsibility of OpportunitySearchService.
    This layer only adds live capital planning and combines market/portfolio
    opportunity results for the next allocation stage.
    """

    def __init__(
        self,
        planning_service: AutonomousPlanningService,
        opportunity_service: OpportunitySearchService,
    ) -> None:
        self._planning = planning_service
        self._opportunities = opportunity_service

    def run(
        self,
        *,
        account_id: str,
        policy: BudgetPlanningPolicy,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
        progress_callback: Callable[[str, float, int, int], None] | None = None,
        result_callback: Callable[[OpportunitySearchResult, int, int], None] | None = None,
    ) -> AutonomousCycleResult:
        planning = self._planning.plan(account_id, policy)
        market = self._opportunities.scan(
            profile=profile,
            instrument_kind=instrument_kind,
            scope=MARKET_SCOPE,
            progress_callback=progress_callback,
            result_callback=result_callback,
        )
        portfolio = self._opportunities.scan(
            profile=profile,
            instrument_kind=instrument_kind,
            scope=PORTFOLIO_SCOPE,
            progress_callback=progress_callback,
            result_callback=result_callback,
        )
        return AutonomousCycleResult(
            planning=planning,
            market_opportunities=tuple(market),
            portfolio_opportunities=tuple(portfolio),
        )
