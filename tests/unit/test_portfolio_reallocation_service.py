from decimal import Decimal
from types import SimpleNamespace

from edward.services.budget_planning_service import BudgetPlan
from edward.services.portfolio_reallocation_service import PortfolioReallocationService, ReallocationPolicy


def budget(slots=2, cash="50000", target="10000"):
    return BudgetPlan(
        account_capital=Decimal("50000"),
        cash=Decimal(cash),
        blocked_cash=Decimal("0"),
        invested=Decimal("20000"),
        reserve=Decimal("5000"),
        planning_budget=Decimal("45000"),
        investable_cash=Decimal(cash),
        slots=slots,
        target_position_value=Decimal(target),
    )


def opportunity(ticker, uid, decision, score, risk, value=0):
    return SimpleNamespace(
        ticker=ticker,
        instrument_uid=uid,
        decision=decision,
        opportunity_score=score,
        risk_score=risk,
        recommended_value=value,
    )


def test_free_slot_gets_best_buy_without_absolute_budget():
    service = PortfolioReallocationService()
    actions = service.plan(
        budget=budget(slots=2, cash="12000", target="10000"),
        market_opportunities=[
            opportunity("AAA", "a", "BUY", 82, 20),
            opportunity("BBB", "b", "BUY", 75, 10),
        ],
        portfolio_opportunities=[opportunity("OLD", "old", "HOLD", 70, 30)],
    )

    buys = [x for x in actions if x.action == "BUY"]
    assert len(buys) == 1
    assert buys[0].ticker == "AAA"
    assert buys[0].target_value == Decimal("10000")


def test_full_portfolio_replaces_weaker_position_with_better_lower_risk():
    service = PortfolioReallocationService(ReallocationPolicy(replacement_score_delta=5.0))
    actions = service.plan(
        budget=budget(slots=2, cash="0", target="10000"),
        market_opportunities=[opportunity("NEW", "new", "BUY", 90, 15)],
        portfolio_opportunities=[
            opportunity("WEAK", "weak", "HOLD", 70, 25),
            opportunity("GOOD", "good", "HOLD", 85, 10),
        ],
    )

    replacements = [x for x in actions if x.action == "REPLACE"]
    assert len(replacements) == 1
    assert replacements[0].ticker == "NEW"
    assert replacements[0].source_ticker == "WEAK"
    assert replacements[0].target_value == Decimal("10000")


def test_replacement_is_blocked_when_risk_is_higher():
    service = PortfolioReallocationService(ReallocationPolicy(replacement_score_delta=5.0))
    actions = service.plan(
        budget=budget(slots=1, cash="0", target="10000"),
        market_opportunities=[opportunity("NEW", "new", "BUY", 95, 40)],
        portfolio_opportunities=[opportunity("HELD", "held", "HOLD", 70, 20)],
    )

    assert not [x for x in actions if x.action == "REPLACE"]
