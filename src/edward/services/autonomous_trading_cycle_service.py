from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from edward.services.account_state_refresh_service import AccountState, AccountStateRefreshService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlanService
from edward.services.autonomous_execution_preflight_service import AutonomousExecutionPreflightService
from edward.services.autonomous_execution_sequence_service import AutonomousExecutionSequenceService
from edward.services.autonomous_execution_verification_service import AutonomousExecutionVerificationService
from edward.services.autonomous_protection_service import AutonomousProtectionService
from edward.services.autonomous_replanning_cycle_service import AutonomousReplanningCycleService
from edward.services.autonomous_execution_service import AutonomousExecutionService
from edward.services.budget_planning_service import BudgetPlanningService
from edward.services.opportunity_search_service import OpportunitySearchService
from edward.services.portfolio_reallocation_service import PortfolioReallocationService


@dataclass(frozen=True, slots=True)
class AutonomousTradingCycleResult:
    cycle_id: str
    status: str
    account_state: AccountState | None = None
    message: str = ""


class AutonomousTradingCycleService:
    """Application-level orchestration boundary for one autonomous trading cycle.

    Existing domain services remain responsible for their own business rules;
    this service only establishes the lifecycle and dependency order.
    """

    def __init__(
        self,
        *,
        account_state_refresh: AccountStateRefreshService,
        opportunity_search: OpportunitySearchService,
        budget_planning: BudgetPlanningService,
        reallocation: PortfolioReallocationService,
        execution_plan: AutonomousExecutionPlanService,
        preflight: AutonomousExecutionPreflightService,
        execution: AutonomousExecutionService,
        sequence: AutonomousExecutionSequenceService,
        verification: AutonomousExecutionVerificationService,
        protection: AutonomousProtectionService,
        replanning: AutonomousReplanningCycleService,
    ) -> None:
        self.account_state_refresh = account_state_refresh
        self.opportunity_search = opportunity_search
        self.budget_planning = budget_planning
        self.reallocation = reallocation
        self.execution_plan = execution_plan
        self.preflight = preflight
        self.execution = execution
        self.sequence = sequence
        self.verification = verification
        self.protection = protection
        self.replanning = replanning

    def run(
        self,
        *,
        cycle_id: str,
        account_id: str,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
        opportunity_scope: str = "MARKET",
        execute: bool = False,
        state_provider: Callable[[], AccountState] | None = None,
    ) -> AutonomousTradingCycleResult:
        """Run the cycle's first orchestration stage.

        Execution is deliberately opt-in here. The method establishes the
        canonical live-state -> analysis entry point without bypassing the
        existing execution gates.
        """
        if not cycle_id:
            raise ValueError("CYCLE_ID_REQUIRED")
        if not account_id:
            raise ValueError("ACCOUNT_ID_REQUIRED")

        state = state_provider() if state_provider is not None else self.account_state_refresh.refresh(account_id)
        if state is None:
            return AutonomousTradingCycleResult(cycle_id, "BLOCKED", None, "ACCOUNT_STATE_UNAVAILABLE")

        if not execute:
            return AutonomousTradingCycleResult(cycle_id, "ANALYSIS_READY", state, "LIVE_STATE_REFRESHED")

        raise NotImplementedError("AUTONOMOUS_EXECUTION_STAGE_NOT_WIRED")


__all__ = ["AutonomousTradingCycleResult", "AutonomousTradingCycleService"]
