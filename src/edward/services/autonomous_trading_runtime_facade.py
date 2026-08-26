from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.domain.execution import ExecutionMode, ExecutionStatus
from edward.services.account_state_refresh_service import AccountState, AccountStateRefreshService
from edward.services.autonomous_cycle_service import AutonomousCycleService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_sequence_service import AutonomousExecutionSequenceService
from edward.services.autonomous_protection_service import AutonomousProtectionService
from edward.services.autonomous_trading_controller import AutonomousTradingControlResult, AutonomousTradingController
from edward.services.autonomous_planning_service import AutonomousPlanningService
from edward.services.balance_service import BalanceService
from edward.services.budget_planning_service import BudgetPlanningPolicy, BudgetPlan
from edward.services.execution_bridge_service_v06 import ExecutionBridgeService
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine
from edward.services.opportunity_search_service import OpportunitySearchService
from edward.services.protection_reconciliation_service import ProtectionReconciliationService
from edward.services.stop_order_service import StopOrderService
from edward.services.tinvest_execution_adapter import TInvestExecutionAdapter


class _EnginePreTradeValidator:
    """Reuse ExecutionEngine's existing validation as the controlled pre-trade gate."""

    def __init__(self, engine: ExecutionEngine) -> None:
        self._engine = engine

    def validate(self, request: Any) -> tuple[bool, tuple[str, ...]]:
        result = self._engine.validate(request)
        if result.status is ExecutionStatus.READY:
            return True, ()
        reason = result.error_message or result.error_code or "EXECUTION_VALIDATION_FAILED"
        return False, tuple(part for part in str(reason).split(";") if part)


@dataclass(frozen=True, slots=True)
class AutonomousRuntimeResult:
    control: AutonomousTradingControlResult


class AutonomousTradingRuntimeFacade:
    """Compose the existing T-Invest execution stack for autonomous runtime use.

    No order/execution logic lives here. This is only dependency wiring between
    the existing adapter, execution engine, controlled bridge, protection,
    replanning controller and the existing analysis/planning services.
    """

    def __init__(
        self,
        client: TInvestAdapterClient,
        *,
        account_id: str,
        policy: BudgetPlanningPolicy,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
    ) -> None:
        self.client = client
        self.account_id = str(account_id)
        self.policy = policy
        self.profile = profile
        self.instrument_kind = instrument_kind

        balance = BalanceService(client)
        planning = AutonomousPlanningService(balance)
        opportunities = OpportunitySearchService(client)

        execution_adapter = TInvestExecutionAdapter(client)
        engine = ExecutionEngine(adapter=execution_adapter)
        validator = _EnginePreTradeValidator(engine)
        controlled = ControlledExecutionService(engine, validator)
        bridge = ExecutionBridgeService(controlled)

        state_refresh = AccountStateRefreshService(
            client,
            balance,
            client,
            client,
        )
        stop_orders = StopOrderService(client)
        protection = AutonomousProtectionService(stop_orders)
        reconciliation = ProtectionReconciliationService(stop_orders)
        sequence = AutonomousExecutionSequenceService(
            bridge,
            state_refresh,
            protection_service=protection,
        )
        controller = AutonomousTradingController(
            sequence,
            protection_reconciliation=reconciliation,
        )
        controller.enable()

        self._planning = planning
        self._opportunities = opportunities
        self._state_refresh = state_refresh
        self._controller = controller
        self._cycle = AutonomousCycleService(
            planning,
            opportunities,
            trading_controller=controller,
        )

    @property
    def controller(self) -> AutonomousTradingController:
        return self._controller

    def run_cycle(self, *, max_iterations: int = 50) -> AutonomousRuntimeResult:
        def refresh_state() -> AccountState:
            return self._state_refresh.refresh(self.account_id)

        def build_plan(_state: AccountState) -> AutonomousExecutionPlan:
            result = self._cycle.run(
                account_id=self.account_id,
                policy=self.policy,
                profile=self.profile,
                instrument_kind=self.instrument_kind,
            )
            return result.execution_plan or AutonomousExecutionPlan(steps=())

        def budget_for_state(_state: AccountState) -> BudgetPlan:
            return self._planning.plan(self.account_id, self.policy).budget

        def result_factory(step: ExecutionPlanStep) -> Any:
            return self._fresh_opportunity(step)

        control = self._cycle.execute_replanned(
            account_id=self.account_id,
            mode=ExecutionMode.AUTONOMOUS,
            refresh_state=refresh_state,
            build_plan=build_plan,
            budget_for_state=budget_for_state,
            result_factory=result_factory,
            max_iterations=max_iterations,
        )
        return AutonomousRuntimeResult(control=control)

    def _fresh_opportunity(self, step: ExecutionPlanStep) -> Any:
        for scope in ("MARKET", "PORTFOLIO"):
            results = self._opportunities.scan(
                profile=self.profile,
                instrument_kind=self.instrument_kind,
                scope=scope,
                force_recompute=True,
            )
            for result in results:
                if str(result.instrument_uid) == str(step.instrument_uid):
                    return result
        raise RuntimeError(f"FRESH_OPPORTUNITY_NOT_FOUND:{step.instrument_uid}")


__all__ = ["AutonomousRuntimeResult", "AutonomousTradingRuntimeFacade"]
