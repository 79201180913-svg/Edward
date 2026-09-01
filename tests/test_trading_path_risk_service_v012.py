from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012
from edward.services.analysis_service import Candle
from edward.services.trading_path_risk_service_v012 import TradingPathRiskServiceV012


def _analysis() -> TradingPathAnalysisV012:
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
    )


def _candles():
    return [
        Candle(i, 100.0, 101.0, 99.0, 100.0 + i * 0.1, 1000.0)
        for i in range(20)
    ]


def test_path_risk_reuses_existing_risk_engine(monkeypatch):
    captured = {}

    def fake_evaluate(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            score=80.0,
            gate=True,
            critical=False,
            reasons=(),
        )

    monkeypatch.setattr("edward.services.trading_path_risk_service_v012.RiskEngine.evaluate", fake_evaluate)

    result = TradingPathRiskServiceV012.evaluate(
        _analysis(),
        candles=_candles(),
        strategy_result=SimpleNamespace(),
        profile="medium_term",
    )

    assert result.path_eligible is True
    assert result.risk.score == 80.0
    assert captured["profile"] == "medium_term"
    assert captured["strategy_result"] is not None


def test_missing_strategy_result_fails_risk_gate(monkeypatch):
    result = TradingPathRiskServiceV012.evaluate(
        _analysis(),
        candles=_candles(),
        strategy_result=None,
        profile="medium_term",
    )

    assert result.path_eligible is False
    assert result.risk.gate is False
    assert "STRATEGY_UNAVAILABLE" in result.risk.reasons
    assert result.reason == "STRATEGY_UNAVAILABLE"
