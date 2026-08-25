from edward.services.decision_engine import (
    Decision,
    DecisionEngine,
    DecisionRequest,
    OpportunityContext,
    PositionContextData,
    Scenario,
    StrategyContextData,
)


def test_open_position_reduce_preserves_strategy_score_from_context():
    request = DecisionRequest(
        scenario=Scenario.SINGLE_INSTRUMENT,
        strategy=StrategyContextData(
            strategy_name="Momentum",
            strategy_score=31.0,
            quality_gate=False,
            available=True,
        ),
        opportunity=OpportunityContext(
            opportunity_score=0.0,
            entry_ok=False,
            risk_ok=True,
            strategy_ok=False,
            market_regime_compatible=True,
        ),
        position=PositionContextData(quantity=10),
        portfolio_allows_add=False,
    )

    result = DecisionEngine.evaluate(request)

    assert result.decision == Decision.REDUCE
    assert result.strategy_name == "Momentum"
    assert result.strategy_score == 31.0
