from __future__ import annotations

from edward.services.decision_engine import (
    Decision,
    DecisionEngine,
    DecisionRequest,
    OpportunityContext,
    PositionContextData,
    Scenario,
)


def test_no_position_buy():
    result = DecisionEngine.evaluate(
        DecisionRequest(
            scenario=Scenario.SINGLE_INSTRUMENT,
            strategy_name="Momentum",
            strategy_score=86.0,
            strategy_quality=True,
            opportunity=OpportunityContext(
                opportunity_score=82.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
            ),
        )
    )
    assert result.decision == Decision.BUY
    assert result.status.value == "VALID"


def test_no_position_wait_when_entry_not_ready():
    result = DecisionEngine.evaluate(
        DecisionRequest(
            strategy_name="Breakout",
            strategy_score=85.0,
            strategy_quality=True,
            opportunity=OpportunityContext(
                opportunity_score=88.0,
                entry_ok=False,
                risk_ok=True,
                strategy_ok=True,
            ),
        )
    )
    assert result.decision == Decision.WAIT
    assert "ENTRY_NOT_READY" in result.reason_codes


def test_no_position_pass_without_strategy():
    result = DecisionEngine.evaluate(
        DecisionRequest(
            strategy_name=None,
            strategy_score=42.0,
            strategy_quality=False,
            opportunity=OpportunityContext(
                opportunity_score=35.0,
                entry_ok=False,
                risk_ok=True,
                strategy_ok=False,
            ),
        )
    )
    assert result.decision == Decision.PASS
    assert result.status.value == "VALID"


def test_open_position_sell_has_priority():
    result = DecisionEngine.evaluate(
        DecisionRequest(
            strategy_name="Trend Following",
            strategy_score=70.0,
            strategy_quality=True,
            exit_signal=True,
            opportunity=OpportunityContext(
                opportunity_score=90.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
            ),
            position=PositionContextData(quantity=100),
        )
    )
    assert result.decision == Decision.SELL


def test_open_position_reduce_when_above_target():
    result = DecisionEngine.evaluate(
        DecisionRequest(
            strategy_name="Trend Following",
            strategy_score=80.0,
            strategy_quality=True,
            opportunity=OpportunityContext(
                opportunity_score=65.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
            ),
            position=PositionContextData(quantity=100, portfolio_weight_pct=18.0, target_weight_pct=10.0),
        )
    )
    assert result.decision == Decision.REDUCE


def test_open_position_add_when_below_target():
    result = DecisionEngine.evaluate(
        DecisionRequest(
            strategy_name="Momentum",
            strategy_score=88.0,
            strategy_quality=True,
            portfolio_allows_add=True,
            opportunity=OpportunityContext(
                opportunity_score=84.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
            ),
            position=PositionContextData(quantity=100, portfolio_weight_pct=4.0, target_weight_pct=10.0),
        )
    )
    assert result.decision == Decision.ADD


def test_open_position_hold_default():
    result = DecisionEngine.evaluate(
        DecisionRequest(
            strategy_name="Momentum",
            strategy_score=78.0,
            strategy_quality=True,
            opportunity=OpportunityContext(
                opportunity_score=58.0,
                entry_ok=False,
                risk_ok=True,
                strategy_ok=True,
            ),
            position=PositionContextData(quantity=100, portfolio_weight_pct=8.0, target_weight_pct=10.0),
        )
    )
    assert result.decision == Decision.HOLD


def test_ranking_buy_before_wait_before_pass():
    requests = [
        DecisionRequest(
            strategy_name="Pass",
            strategy_quality=False,
            opportunity=OpportunityContext(opportunity_score=95, risk_ok=True, strategy_ok=False),
        ),
        DecisionRequest(
            strategy_name="Wait",
            strategy_score=70,
            strategy_quality=True,
            opportunity=OpportunityContext(opportunity_score=55, entry_ok=True, risk_ok=True, strategy_ok=True),
        ),
        DecisionRequest(
            strategy_name="Buy",
            strategy_score=90,
            strategy_quality=True,
            opportunity=OpportunityContext(opportunity_score=90, entry_ok=True, risk_ok=True, strategy_ok=True),
        ),
    ]
    results = DecisionEngine.rank_opportunities(requests)
    assert [item.decision for item in results] == [Decision.BUY, Decision.WAIT, Decision.PASS]
