from decimal import Decimal
from types import SimpleNamespace

from edward.services.autonomous_replanning_service import AutonomousReplanningService
from edward.services.balance_service import FinancialSummary
from edward.services.budget_planning_service import BudgetPlanningPolicy


def financial(capital, cash, securities):
    return FinancialSummary(
        currency="RUB",
        available=Decimal(cash),
        blocked=Decimal("0"),
        cash=Decimal(cash),
        securities=Decimal(securities),
        portfolio_value=Decimal(capital),
    )


def opportunity(ticker, uid, decision, score, risk):
    return SimpleNamespace(
        ticker=ticker,
        instrument_uid=uid,
        decision=decision,
        opportunity_score=score,
        risk_score=risk,
        recommended_value=Decimal("0"),
    )


def test_replan_uses_current_capital_after_portfolio_change():
    service = AutonomousReplanningService()
    result = service.replan(
        financial=financial("120000", "90000", "30000"),
        policy=BudgetPlanningPolicy(slots=5, reserve_pct=Decimal("10")),
        market_opportunities=[opportunity("AAA", "aaa", "BUY", 90, 10)],
        portfolio_opportunities=[],
    )

    assert result.budget.account_capital == Decimal("120000.00")
    assert result.budget.reserve == Decimal("12000.00")
    assert result.budget.planning_budget == Decimal("108000.00")
    assert result.budget.target_position_value == Decimal("21600.00")
    assert result.actions[0].ticker == "AAA"
    assert result.actions[0].target_value == Decimal("21600.00")


def test_replan_can_use_newly_freed_cash_for_next_opportunity():
    service = AutonomousReplanningService()
    result = service.replan(
        financial=financial("100000", "100000", "0"),
        policy=BudgetPlanningPolicy(slots=2, reserve_pct=Decimal("10")),
        market_opportunities=[
            opportunity("AAA", "aaa", "BUY", 95, 10),
            opportunity("BBB", "bbb", "BUY", 80, 10),
        ],
        portfolio_opportunities=[],
    )

    buys = [action for action in result.actions if action.action == "BUY"]
    assert [action.ticker for action in buys] == ["AAA", "BBB"]
    assert sum((action.target_value for action in buys), Decimal("0")) == Decimal("90000.00")


def test_replan_re_evaluates_replacement_against_current_portfolio():
    service = AutonomousReplanningService()
    result = service.replan(
        financial=financial("100000", "0", "100000"),
        policy=BudgetPlanningPolicy(slots=1, reserve_pct=Decimal("0")),
        market_opportunities=[opportunity("NEW", "new", "BUY", 90, 10)],
        portfolio_opportunities=[opportunity("OLD", "old", "HOLD", 70, 20)],
    )

    replacements = [action for action in result.actions if action.action == "REPLACE"]
    assert len(replacements) == 1
    assert replacements[0].source_ticker == "OLD"
    assert replacements[0].ticker == "NEW"
