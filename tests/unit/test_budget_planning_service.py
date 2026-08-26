from decimal import Decimal

import pytest

from edward.services.balance_service import FinancialSummary
from edward.services.budget_planning_service import BudgetPlanningPolicy, BudgetPlanningService


def financial(*, capital: str, cash: str, securities: str, blocked: str = "0") -> FinancialSummary:
    return FinancialSummary(
        currency="RUB",
        available=Decimal(cash),
        blocked=Decimal(blocked),
        cash=Decimal(cash),
        securities=Decimal(securities),
        portfolio_value=Decimal(capital),
    )


def test_budget_is_derived_from_live_capital_not_hardcoded_amount():
    plan = BudgetPlanningService().build(
        financial(capital="50000", cash="30000", securities="20000"),
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
    )

    assert plan.account_capital == Decimal("50000.00")
    assert plan.reserve == Decimal("5000.00")
    assert plan.planning_budget == Decimal("45000.00")
    assert plan.investable_cash == Decimal("25000.00")
    assert plan.target_position_value == Decimal("9000.00")


def test_budget_recalculates_when_account_capital_changes():
    service = BudgetPlanningService()
    policy = BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10"))

    small = service.build(financial(capital="50000", cash="50000", securities="0"), policy)
    large = service.build(financial(capital="120000", cash="120000", securities="0"), policy)

    assert small.planning_budget == Decimal("45000.00")
    assert large.planning_budget == Decimal("108000.00")
    assert large.target_position_value == Decimal("21600.00")


def test_existing_securities_are_not_double_counted_as_spendable_cash():
    plan = BudgetPlanningService().build(
        financial(capital="100000", cash="60000", securities="40000"),
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
    )

    assert plan.planning_budget == Decimal("90000.00")
    assert plan.invested == Decimal("40000.00")
    assert plan.investable_cash == Decimal("50000.00")


def test_zero_cash_does_not_create_spendable_budget():
    plan = BudgetPlanningService().build(
        financial(capital="100000", cash="0", securities="100000"),
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
    )

    assert plan.planning_budget == Decimal("90000.00")
    assert plan.investable_cash == Decimal("0.00")


def test_policy_rejects_invalid_values():
    with pytest.raises(ValueError):
        BudgetPlanningPolicy(slots=0)
    with pytest.raises(ValueError):
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("101"))
    with pytest.raises(ValueError):
        BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("-1"))
