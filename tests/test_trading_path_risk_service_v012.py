from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012
from edward.services.analysis_service import Candle
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSWindowV012
from edward.services.trading_path_risk_service_v012 import TradingPathRiskServiceV012


def _analysis():
    return TradingPathAnalysisV012(
        instrument_uid="uid-1", ticker="SBER", strategy_family="Breakout",
        hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP", volatility_bucket="Normal",
        direction="Positive", horizon=5, evidence=SimpleNamespace(),
    )


def _candles():
    return [Candle(i, 100.0, 101.0, 99.0, 100.0 + i * 0.1, 1000.0) for i in range(40)]


def _windows():
    return (
        TradingPathOOSWindowV012(1, 0, 10, 3, 1.0, 0.2, 0.8, 66.7, True, (1.0, 0.5, -0.2)),
        TradingPathOOSWindowV012(2, 10, 20, 3, 0.8, 0.1, 0.7, 66.7, True, (0.8, 0.4, -0.1)),
    )


def test_risk_can_be_derived_from_path_oos_evidence(monkeypatch):
    captured = {}

    def fake_evaluate(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(score=80.0, gate=True, critical=False, reasons=())

    monkeypatch.setattr("edward.services.trading_path_risk_service_v012.RiskEngine.evaluate", fake_evaluate)
    result = TradingPathRiskServiceV012.evaluate(
        _analysis(), candles=_candles(), profile="medium_term", oos_windows=_windows()
    )

    projected = captured["strategy_result"]
    assert result.path_eligible is True
    assert projected.parameters["path_hypothesis"] == "BREAKOUT_EXPANSION"
    assert projected.trades == 6
    assert projected.wf_windows == 2
    assert projected.stability == 100.0


def test_empty_path_oos_evidence_fails_closed():
    result = TradingPathRiskServiceV012.evaluate(
        _analysis(), candles=_candles(), profile="medium_term", oos_windows=()
    )
    assert result.path_eligible is False
    assert result.risk.gate is False
    assert "STRATEGY_UNAVAILABLE" in result.risk.reasons
