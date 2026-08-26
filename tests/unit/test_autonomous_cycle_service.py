from decimal import Decimal

from edward.services.autonomous_cycle_service import AutonomousCycleService
from edward.services.autonomous_planning_service import AutonomousPlanningResult
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
