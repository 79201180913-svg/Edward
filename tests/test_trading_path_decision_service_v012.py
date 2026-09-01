from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012, TradingPathOpportunity
from edward.services.trading_path_decision_service_v012 import (
    TradingPathDecisionServiceV012,
    TradingPathDecisionV012,
)


def _analysis(*, score=80.0, confidence=80.0, ev=1.5, risk_gate=True, rejected=False, positive_oos=80.0):
    validation = SimpleNamespace(
        promotion_status="REJECTED" if rejected else "VALIDATED",
        positive_oos_windows_pct=positive_oos,
    )
    return TradingPathAnalysisV012(
        instrument_uid="uid-1",
        ticker="SBER",
        strategy_family="Breakout",
        hypothesis="BREAKOUT_EXPANSION",
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
        evidence=SimpleNamespace(),
        validation=validation,
        opportunity=TradingPathOpportunity(
            score=score,
            confidence=confidence,
            expected_value_pct=ev,
            risk_score=80.0,
            risk_gate=risk_gate,
        ),
    )


def test_strong_path_can_be_entry_ready():
    result = TradingPathDecisionServiceV012.decide(_analysis())
    assert result.decision is TradingPathDecisionV012.BUY
    assert result.reasons == ()


def test_missing_score_waits():
    result = TradingPathDecisionServiceV012.decide(_analysis(score=None))
    assert result.decision is TradingPathDecisionV012.WAIT
    assert "OPPORTUNITY_SCORE_UNAVAILABLE" in result.reasons


def test_failed_risk_gate_passes_path():
    result = TradingPathDecisionServiceV012.decide(_analysis(risk_gate=False))
    assert result.decision is TradingPathDecisionV012.PASS
    assert "RISK_GATE_FAILED" in result.reasons


def test_rejected_validation_passes_path():
    result = TradingPathDecisionServiceV012.decide(_analysis(rejected=True))
    assert result.decision is TradingPathDecisionV012.PASS
    assert "PATH_VALIDATION_REJECTED" in result.reasons


def test_low_confidence_waits():
    result = TradingPathDecisionServiceV012.decide(_analysis(confidence=20.0))
    assert result.decision is TradingPathDecisionV012.WAIT
    assert "CONFIDENCE_BELOW_THRESHOLD" in result.reasons
