from decimal import Decimal

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_live_execution_service import AutonomousLiveExecutionService
from edward.services.autonomous_planning_service import AutonomousPlanningResult
from edward.services.budget_planning_service import BudgetPlan, BudgetPlanningPolicy


class FakeState:
    def __init__(self):
        self.calls = 0

    def refresh(self, account_id):
        self.calls += 1
        return AccountState(portfolio=None, positions=[], balance=None, orders=[])


class FakePlanning:
    def plan(self, account_id, policy):
        return AutonomousPlanningResult(
            account_id=account_id,
            budget=BudgetPlan(
                account_capital=Decimal("100000"),
                cash=Decimal("100000"),
                blocked_cash=Decimal("0"),
                invested=Decimal("0"),
                reserve=Decimal("10000"),
                planning_budget=Decimal("90000"),
                investable_cash=Decimal("90000"),
                slots=policy.slots,
                target_position_value=Decimal("18000"),
            ),
        )


class FakeOpportunities:
    def __init__(self):
        self.scopes = []

    def scan(self, **kwargs):
        self.scopes.append(kwargs["scope"])
        return []


class FakeReallocation:
    def plan(self, **kwargs):
        return []


class FakePlanBuilder:
    def build(self, actions):
        return AutonomousExecutionPlan(steps=())


class FakeController:
    def __init__(self):
        self.calls = []

    def execute_replanned(self, **kwargs):
        self.calls.append(kwargs)
        kwargs["refresh_state"]()
        kwargs["build_plan"](AccountState(portfolio=None, positions=[], balance=None, orders=[]))
        return type("Control", (), {"executed": False, "reason": "COMPLETED"})()


def test_analysis_mode_reuses_existing_services_without_execution():
    state = FakeState()
    opportunities = FakeOpportunities()
    controller = FakeController()
    service = AutonomousLiveExecutionService(
        account_state=state,
        planning=FakePlanning(),
        opportunities=opportunities,
        reallocation=FakeReallocation(),
        execution_controller=controller,
        execution_plan_builder=FakePlanBuilder(),
    )

    result = service.run(
        account_id="ACC",
        policy=BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
        mode=ExecutionMode.ANALYSIS_ONLY,
    )

    assert len(controller.calls) == 1
    assert opportunities.scopes == ["MARKET", "PORTFOLIO"]
    assert result.plans_built == 1
    assert result.opportunities_scanned == 0


def test_fresh_result_factory_is_not_called_when_external_factory_is_supplied():
    controller = FakeController()
    service = AutonomousLiveExecutionService(
        account_state=FakeState(),
        planning=FakePlanning(),
        opportunities=FakeOpportunities(),
        reallocation=FakeReallocation(),
        execution_controller=controller,
        execution_plan_builder=FakePlanBuilder(),
    )

    result_factory = lambda step: object()
    service.run(
        account_id="ACC",
        policy=BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
        result_factory=result_factory,
    )

    assert controller.calls[0]["result_factory"] is not None
