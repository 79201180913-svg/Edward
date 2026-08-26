from decimal import Decimal

import pytest

from edward.domain.execution import ExecutionMode
from edward.services.autonomous_cycle_service import AutonomousCycleService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_planning_service import AutonomousPlanningResult
from edward.services.autonomous_trading_controller import AutonomousTradingControlResult
from edward.services.budget_planning_service import BudgetPlan, BudgetPlanningPolicy


class FakePlanning:
    def plan(self, account_id, policy):
        budget = BudgetPlan(
            account_capital=Decimal("100000"),
            cash=Decimal("90000"),
            blocked_cash=Decimal("0"),
            invested=Decimal("10000"),
            reserve=Decimal("10000"),
            planning_budget=Decimal("90000"),
            investable_cash=Decimal("80000"),
            slots=policy.slots,
            target_position_value=Decimal("18000"),
        )
        return AutonomousPlanningResult(account_id=account_id, budget=budget)


class FakeOpportunities:
    def __init__(self):
        self.scopes = []

    def scan(self, **kwargs):
        self.scopes.append(kwargs["scope"])
        return [f"{kwargs['scope']}-result"]


class FakeController:
    def __init__(self):
        self.calls = []

    def execute_replanned(self, **kwargs):
        self.calls.append(kwargs)
        return AutonomousTradingControlResult(
            mode=kwargs["mode"], executed=True, reason="COMPLETED"
        )


def make_cycle(controller=None):
    return AutonomousCycleService(FakePlanning(), FakeOpportunities(), trading_controller=controller)


def test_cycle_reuses_opportunity_service_for_market_and_portfolio():
    opportunities = FakeOpportunities()
    cycle = AutonomousCycleService(FakePlanning(), opportunities)

    result = cycle.run(
        account_id="ACC",
        policy=BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
    )

    assert result.planning.account_id == "ACC"
    assert result.planning.budget.planning_budget == Decimal("90000")
    assert opportunities.scopes == ["MARKET", "PORTFOLIO"]
    assert result.market_opportunities == ("MARKET-result",)
    assert result.portfolio_opportunities == ("PORTFOLIO-result",)


def test_execute_replanned_delegates_to_existing_controller():
    controller = FakeController()
    cycle = make_cycle(controller)
    expected_plan = AutonomousExecutionPlan(steps=())
    refresh = lambda: "state"
    build = lambda state: expected_plan
    budget = lambda state: "budget"
    factory = lambda step: step

    result = cycle.execute_replanned(
        account_id="ACC",
        mode=ExecutionMode.AUTONOMOUS,
        refresh_state=refresh,
        build_plan=build,
        budget_for_state=budget,
        result_factory=factory,
    )

    assert result.executed is True
    assert result.reason == "COMPLETED"
    assert len(controller.calls) == 1
    assert controller.calls[0]["account_id"] == "ACC"
    assert controller.calls[0]["refresh_state"] is refresh
    assert controller.calls[0]["build_plan"] is build
    assert controller.calls[0]["budget_for_state"] is budget
    assert controller.calls[0]["result_factory"] is factory


def test_execute_replanned_requires_controller():
    cycle = make_cycle()
    with pytest.raises(RuntimeError, match="AUTONOMOUS_TRADING_CONTROLLER_REQUIRED"):
        cycle.execute_replanned(
            account_id="ACC",
            mode=ExecutionMode.AUTONOMOUS,
            refresh_state=lambda: "state",
            build_plan=lambda state: AutonomousExecutionPlan(steps=()),
            budget_for_state=lambda state: "budget",
            result_factory=lambda step: step,
        )
