from decimal import Decimal

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_trading_runtime_facade import AutonomousTradingRuntimeFacade
from edward.services.budget_planning_service import BudgetPlan


def test_budget_for_state_uses_refreshed_positions_and_portfolio(monkeypatch):
    facade = object.__new__(AutonomousTradingRuntimeFacade)

    class FakePlanning:
        def __init__(self):
            self.calls = []

        def plan_from_state(self, account_id, policy, *, positions, portfolio):
            self.calls.append((account_id, policy, positions, portfolio))
            return type("PlanningResult", (), {"budget": BudgetPlan(
                account_capital=Decimal("100000"),
                cash=Decimal("90000"),
                blocked_cash=Decimal("0"),
                invested=Decimal("10000"),
                reserve=Decimal("10000"),
                planning_budget=Decimal("90000"),
                investable_cash=Decimal("80000"),
                slots=policy.slots,
                target_position_value=Decimal("18000"),
            )})()

    planning = FakePlanning()
    facade._planning = planning
    facade.account_id = "ACC"
    facade.policy = type("Policy", (), {"slots": 5})()

    positions = ["position"]
    portfolio = {"portfolio": "snapshot"}
    state = AccountState(portfolio=portfolio, positions=positions, balance=None, orders=[])

    # Exercise the exact callback contract used by run_cycle without making
    # any market/API calls or executing an order.
    budget = facade._planning.plan_from_state(
        facade.account_id,
        facade.policy,
        positions=state.positions,
        portfolio=state.portfolio,
    ).budget

    assert budget.investable_cash == Decimal("80000")
    assert planning.calls == [("ACC", facade.policy, positions, portfolio)]
