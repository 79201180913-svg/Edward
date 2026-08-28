from decimal import Decimal
from types import SimpleNamespace

from edward.services.budget_planning_service import BudgetPlan
from edward.services.portfolio_reallocation_service import PortfolioReallocationService


def make_budget():
    return BudgetPlan(
        account_capital=Decimal("50000"),
        cash=Decimal("20000"),
        blocked_cash=Decimal("0"),
        invested=Decimal("30000"),
        reserve=Decimal("5000"),
        planning_budget=Decimal("45000"),
        investable_cash=Decimal("20000"),
        slots=3,
        target_position_value=Decimal("10000"),
    )


def opportunity(ticker, uid, decision, score, risk):
    return SimpleNamespace(
        ticker=ticker,
        instrument_uid=uid,
        decision=decision,
        opportunity_score=score,
        risk_score=risk,
        recommended_value=0,
    )


def test_market_buy_for_held_instrument_is_not_created():
    service = PortfolioReallocationService()

    actions = service.plan(
        budget=make_budget(),
        market_opportunities=[
            opportunity("HELD", "held", "BUY", 95, 10),
            opportunity("NEW", "new", "BUY", 90, 10),
        ],
        portfolio_opportunities=[
            opportunity("HELD", "held", "HOLD", 80, 15),
        ],
    )

    buys = [action for action in actions if action.action == "BUY"]
    assert [action.ticker for action in buys] == ["NEW"]
