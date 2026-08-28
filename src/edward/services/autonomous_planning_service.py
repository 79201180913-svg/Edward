from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.balance_service import BalanceService
from edward.services.budget_planning_service import BudgetPlan, BudgetPlanningPolicy, BudgetPlanningService


@dataclass(frozen=True, slots=True)
class AutonomousPlanningResult:
    account_id: str
    budget: BudgetPlan


class AutonomousPlanningService:
    """Build the autonomous capital plan from the live account state.

    This service deliberately orchestrates existing account/balance services;
    it does not fetch market data, analyse instruments, rank opportunities or
    execute orders.
    """

    def __init__(
        self,
        balance_service: BalanceService,
        budget_service: BudgetPlanningService | None = None,
    ) -> None:
        self._balance_service = balance_service
        self._budget_service = budget_service or BudgetPlanningService()

    def plan(self, account_id: str, policy: BudgetPlanningPolicy) -> AutonomousPlanningResult:
        """Build a plan from a freshly fetched account state.

        This remains the compatibility entry point for callers that do not
        already own a state snapshot.
        """
        positions = self._balance_service.get_positions(account_id)
        portfolio = self._balance_service.get_portfolio(account_id)
        return self.plan_from_state(
            account_id,
            policy,
            positions=positions,
            portfolio=portfolio,
        )

    def plan_from_state(
        self,
        account_id: str,
        policy: BudgetPlanningPolicy,
        *,
        positions: Any,
        portfolio: Any,
    ) -> AutonomousPlanningResult:
        """Build the budget exclusively from the supplied account snapshot.

        Autonomous replanning must use the state snapshot that was just
        refreshed and verified. This method therefore performs no additional
        account/API reads.
        """
        financial = self._balance_service.build_summary(positions, portfolio)
        budget = self._budget_service.build(financial, policy)
        return AutonomousPlanningResult(account_id=account_id, budget=budget)
