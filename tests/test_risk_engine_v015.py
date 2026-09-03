from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.risk_engine import RiskEngine


def _candles():
    return [Candle(i, 100.0, 101.0, 99.0, 100.0 + i * 0.1, 1000.0) for i in range(40)]


def _strategy(max_drawdown_pct=0.0, sharpe=2.0):
    return SimpleNamespace(max_drawdown_pct=max_drawdown_pct, sharpe=sharpe)


def test_drawdown_limit_is_hard_even_when_score_is_positive():
    result = RiskEngine.evaluate(
        strategy_result=_strategy(max_drawdown_pct=26.0),
        candles=_candles(),
        profile="medium_term",
    )
    assert result.score >= 0.0
    assert result.gate is False
    assert result.critical is True
    assert "MAX_DRAWDOWN_LIMIT" in result.reasons


def test_position_weight_limit_is_hard():
    result = RiskEngine.evaluate(
        strategy_result=_strategy(),
        candles=_candles(),
        profile="medium_term",
        target_weight_pct=10.0,
        position_weight_pct=16.0,
    )
    assert result.gate is False
    assert result.critical is True
    assert "POSITION_WEIGHT_LIMIT" in result.reasons


def test_clean_risk_can_pass_without_score_being_a_gate():
    result = RiskEngine.evaluate(
        strategy_result=_strategy(),
        candles=_candles(),
        profile="medium_term",
    )
    assert result.gate is True
    assert result.critical is False
    assert result.reasons == ()
