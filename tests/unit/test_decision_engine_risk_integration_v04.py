from edward.services.decision_engine import (
    Decision,
    DecisionEngine,
    DecisionRequest,
    InstrumentContextData,
    MarketContextData,
    OpportunityContext,
    PositionContextData,
    RiskContextData,
    Scenario,
    StrategyContextData,
)


def _request(*, risk_gate: bool, risk_score: float, opportunity_score: float, position: bool = False) -> DecisionRequest:
    return DecisionRequest(
        scenario=Scenario.SINGLE_INSTRUMENT,
        instrument=InstrumentContextData(buy_available=True, sell_available=True),
        market=MarketContextData(market_regime="Trend", regime_compatible=True, entry_ok=True),
        strategy=StrategyContextData(strategy_name="Trend Following", strategy_score=80.0, quality_gate=True, entry_signal=True),
        risk=RiskContextData(risk_gate=risk_gate, critical_risk=not risk_gate, risk_score=risk_score, available=True),
        opportunity=OpportunityContext(
            opportunity_score=opportunity_score,
            entry_ok=True,
            risk_ok=risk_gate,
            strategy_ok=True,
            market_regime_compatible=True,
            critical_risk=not risk_gate,
        ),
        position=PositionContextData(quantity=10 if position else 0),
        portfolio_allows_buy=not position,
        portfolio_allows_add=position,
        profile="medium_term",
    )


def test_final_decision_blocks_buy_when_risk_gate_fails():
    result = DecisionEngine.evaluate(_request(risk_gate=False, risk_score=28.0, opportunity_score=86.0))
    assert result.decision == Decision.PASS
    assert result.reason_codes[0] == "RISK_FAIL"


def test_final_decision_buys_when_opportunity_and_risk_are_good():
    result = DecisionEngine.evaluate(_request(risk_gate=True, risk_score=82.0, opportunity_score=86.0))
    assert result.decision == Decision.BUY


def test_final_decision_reduces_open_position_when_risk_gate_fails():
    result = DecisionEngine.evaluate(_request(risk_gate=False, risk_score=28.0, opportunity_score=86.0, position=True))
    assert result.decision == Decision.SELL or result.decision == Decision.REDUCE
    assert result.reason_codes[0] in {"RISK_DETERIORATION", "CRITICAL_RISK"}
