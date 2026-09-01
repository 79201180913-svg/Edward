from edward.domain import TradingPathAnalysisV012, TradingPathOpportunity
from edward.services.trading_path_opportunity_builder_v012 import TradingPathOpportunityBuilderV012


def _analysis() -> TradingPathAnalysisV012:
    return TradingPathAnalysisV012(
        instrument_uid="uid-1",
        ticker="SBER",
        strategy_family="Momentum",
        hypothesis="IMPULSE_CONTINUATION",
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
        evidence=object(),
    )


def test_from_components_builds_path_level_opportunity():
    result = TradingPathOpportunityBuilderV012.from_components(
        _analysis(),
        expected_value_pct=0.8,
        risk_score=72.0,
        risk_gate=True,
        score=68.5,
        confidence=81.0,
    )

    assert result.opportunity == TradingPathOpportunity(
        score=68.5,
        confidence=81.0,
        expected_value_pct=0.8,
        risk_score=72.0,
        risk_gate=True,
    )
    assert result.hypothesis == "IMPULSE_CONTINUATION"
    assert result.strategy_family == "Momentum"
    assert result.decision.value == "wait"


def test_builder_does_not_promote_or_create_trade_decision():
    result = TradingPathOpportunityBuilderV012.from_components(
        _analysis(),
        expected_value_pct=3.0,
        risk_score=95.0,
        risk_gate=True,
        score=99.0,
        confidence=99.0,
    )

    assert result.current_state.value == "wait"
    assert result.decision.value == "wait"
    assert result.status.value == "discovered"


def test_builder_accepts_unavailable_components_without_inventing_values():
    result = TradingPathOpportunityBuilderV012.from_components(
        _analysis(),
        expected_value_pct=None,
        risk_score=None,
        risk_gate=None,
    )

    assert result.opportunity.expected_value_pct is None
    assert result.opportunity.risk_score is None
    assert result.opportunity.risk_gate is None
    assert result.opportunity.score is None
