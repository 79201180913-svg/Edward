from decimal import Decimal

from edward.services.autonomous_planning_service import AutonomousPlanningService
from edward.services.balance_service import BalanceService
from edward.services.budget_planning_service import BudgetPlanningPolicy


class FakeBalanceService(BalanceService):
    def __init__(self):
        pass

    def get_positions(self, account_id):
        return {
            "money": [{"currency": "RUB", "available": {"units": 90000, "nano": 0}, "blocked": {"units": 0, "nano": 0}}],
            "securities": [
                {"instrument_uid": "A", "current_value": {"units": 10000, "nano": 0}},
            ],
        }

    def get_portfolio(self, account_id):
        return {"total_amount_portfolio": {"units": 100000, "nano": 0}}


def test_builds_budget_from_live_account_state():
    result = AutonomousPlanningService(FakeBalanceService()).plan(
        "ACC",
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
    )

    assert result.account_id == "ACC"
    assert result.budget.account_capital == Decimal("100000.00")
    assert result.budget.cash == Decimal("90000.00")
    assert result.budget.invested == Decimal("10000.00")
    assert result.budget.reserve == Decimal("10000.00")
    assert result.budget.planning_budget == Decimal("90000.00")
    assert result.budget.investable_cash == Decimal("80000.00")
    assert result.budget.target_position_value == Decimal("18000.00")


def test_budget_changes_with_actual_account_value():
    class ChangingBalance(FakeBalanceService):
        def get_positions(self, account_id):
            return {
                "money": [{"currency": "RUB", "available": {"units": 37000, "nano": 0}, "blocked": {"units": 0, "nano": 0}}],
                "securities": [],
            }

        def get_portfolio(self, account_id):
            return {"total_amount_portfolio": {"units": 37000, "nano": 0}}

    result = AutonomousPlanningService(ChangingBalance()).plan(
        "ACC",
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
    )

    assert result.budget.account_capital == Decimal("37000.00")
    assert result.budget.planning_budget == Decimal("33300.00")
    assert result.budget.target_position_value == Decimal("6660.00")


def test_plan_from_state_does_not_fetch_account_again():
    class CountingBalance(FakeBalanceService):
        def __init__(self):
            self.positions_calls = 0
            self.portfolio_calls = 0

        def get_positions(self, account_id):
            self.positions_calls += 1
            raise AssertionError("plan_from_state must not fetch positions")

        def get_portfolio(self, account_id):
            self.portfolio_calls += 1
            raise AssertionError("plan_from_state must not fetch portfolio")

    service = CountingBalance()
    result = AutonomousPlanningService(service).plan_from_state(
        "ACC",
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
        positions={
            "money": [{"currency": "RUB", "available": {"units": 50000, "nano": 0}, "blocked": {"units": 0, "nano": 0}}],
            "securities": [],
        },
        portfolio={"total_amount_portfolio": {"units": 50000, "nano": 0}},
    )

    assert result.budget.account_capital == Decimal("50000.00")
    assert result.budget.planning_budget == Decimal("45000.00")
    assert service.positions_calls == 0
    assert service.portfolio_calls == 0
