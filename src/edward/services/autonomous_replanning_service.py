from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from edward.services.balance_service import FinancialSummary
from edward.services.budget_planning_service import (
    BudgetPlan,
    BudgetPlanningPolicy,
    BudgetPlanningService,
)
from edward.services.portfolio_reallocation_service import (
    AllocationAction,
    PortfolioReallocationService,
)


@dataclass(frozen=True, slots=True)
class AutonomousReplanningResult:
    """A new allocation decision calculated from a fresh account snapshot."""

    budget: BudgetPlan
    actions: tuple[AllocationAction, ...]


class AutonomousReplanningService:
    """Rebuild the remaining autonomous allocation from current live state.

    The service intentionally composes the existing budget and portfolio
    reallocation services. It does not fetch candles, run analysis, or execute
    orders. Market and portfolio opportunities are expected to come from the
    already existing analysis/opportunity services.
    """

    def __init__(
        self,
        *,
        budget_service: BudgetPlanningService | None = None,
        reallocation_service: PortfolioReallocationService | None = None,
    ) -> None:
        self._budget = budget_service or BudgetPlanningService()
        self._reallocation = reallocation_service or PortfolioReallocationService()

    def replan(
        self,
        *,
        financial: FinancialSummary,
        policy: BudgetPlanningPolicy,
        market_opportunities: Iterable[object],
        portfolio_opportunities: Iterable[object],
    ) -> AutonomousReplanningResult:
        """Calculate a new budget and allocation from the supplied live snapshot."""
        budget = self._budget.build(financial, policy)
        actions = self._reallocation.plan(
            budget=budget,
            market_opportunities=market_opportunities,
            portfolio_opportunities=portfolio_opportunities,
        )
        return AutonomousReplanningResult(budget=budget, actions=actions)


__all__ = ["AutonomousReplanningResult", "AutonomousReplanningService"]
