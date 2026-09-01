from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012, TradingPathOpportunity, TradingPathValidationSummary
from edward.services.trading_path_opportunity_builder_v012 import TradingPathOpportunityBuilderV012
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSWindowV012


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
        validation=TradingPathValidationSummary(
            wf_persistence_pct=75.0,
            robustness_score=80.0,
            positive_oos_windows_pct=75.0,
        ),
    )


def _ev(value=2.0, reliability=80.0):
    return SimpleNamespace(expected_value_pct=value, edge_reliability_pct=reliability)


def _windows():
    return (
        TradingPathOOSWindowV012(1, 0, 10, 5, 2.0, 0.5, 1.5, 60.0, True, (1.0, 2.0)),
        TradingPathOOSWindowV012(2, 10, 20, 5, 1.5, 0.5, 1.0, 60.0, True, (1.0, 2.0)),
        TradingPathOOSWindowV012(3, 20, 30, 5, 0.5, 0.5, 0.0, 50.0, False, (0.0, 1.0)),
        TradingPathOOSWindowV012(4, 30, 40, 5, 1.0, 0.5, 0.5, 60.0, True, (1.0, 1.0)),
    )


def test_score_path_uses_only_path_level_components():
    result = TradingPathOpportunityBuilderV012.score_path(
        _analysis(), expected_value=_ev(), risk_score=70.0, risk_gate=True, oos_windows=_windows()
    )

    # EV=66, risk=70, validation=(75+80+75+75)/4=76.25, confidence=80.
    expected = round(66.0 * 0.35 + 70.0 * 0.25 + 76.25 * 0.25 + 80.0 * 0.15, 2)
    assert result.score == expected
    assert result.expected_value_pct == 2.0
    assert result.risk_score == 70.0
    assert result.confidence == 80.0
    assert result.risk_gate is True


def test_score_path_does_not_invent_score_when_component_is_missing():
    result = TradingPathOpportunityBuilderV012.score_path(
        _analysis(), expected_value=_ev(), risk_score=None, risk_gate=None, oos_windows=_windows()
    )

    assert result.score is None
    assert result.risk_score is None
    assert result.risk_gate is None


def test_build_attaches_opportunity_without_creating_decision():
    result = TradingPathOpportunityBuilderV012.build(
        _analysis(), expected_value=_ev(3.0, 90.0), risk_score=85.0, risk_gate=True, oos_windows=_windows()
    )

    assert result.opportunity.score is not None
    assert result.opportunity.expected_value_pct == 3.0
    assert result.current_state.value == "wait"
    assert result.decision.value == "wait"
    assert result.status.value == "discovered"


def test_from_components_remains_compatible():
    result = TradingPathOpportunityBuilderV012.from_components(
        _analysis(), expected_value_pct=0.8, risk_score=72.0, risk_gate=True, score=68.5, confidence=81.0
    )

    assert result.opportunity == TradingPathOpportunity(
        score=68.5, confidence=81.0, expected_value_pct=0.8, risk_score=72.0, risk_gate=True
    )
    assert result.decision.value == "wait"
