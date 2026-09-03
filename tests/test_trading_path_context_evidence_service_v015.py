from types import SimpleNamespace

from edward.domain import TradingPathContextV015
from edward.services.trading_path_context_evidence_service_v015 import TradingPathContextEvidenceServiceV015


def test_context_evidence_service_consumes_preserved_context_sources(monkeypatch):
    captured = {}

    def fake_analyze(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(version="test")

    monkeypatch.setattr(
        "edward.services.trading_path_context_evidence_service_v015.MultiFactorAnalysisServiceV081.analyze",
        fake_analyze,
    )

    context = TradingPathContextV015(
        fundamentals=object(),
        order_book=object(),
        trades=(object(),),
        current_signal=object(),
        historical_signals=(object(),),
        events=object(),
        historical_gaps_pct=(1.0,),
        historical_event_vol_pct=(2.0,),
        dividends=object(),
        insider=(object(),),
        session_name="REGULAR",
        session_execution_allowed=False,
        risk_metadata=object(),
        current_price=101.0,
        current_weight_pct=5.0,
        marginal_risk_pct=2.0,
        diversification_benefit_pct=3.0,
        expected_return_impact_pct=4.0,
        max_position_weight_pct=10.0,
    )
    candles = (object(), object())

    result = TradingPathContextEvidenceServiceV015.analyze(context=context, candles=candles)

    assert result.version == "test"
    assert captured["fundamentals"] is context.fundamentals
    assert captured["order_book"] is context.order_book
    assert captured["trades"] is context.trades
    assert captured["current_signal"] is context.current_signal
    assert captured["historical_signals"] is context.historical_signals
    assert captured["event"] is context.events
    assert captured["historical_gaps_pct"] is context.historical_gaps_pct
    assert captured["historical_event_vol_pct"] is context.historical_event_vol_pct
    assert captured["dividend_data"] is context.dividends
    assert captured["insider_transactions"] is context.insider
    assert captured["session_name"] == "REGULAR"
    assert captured["session_execution_allowed"] is False
    assert captured["risk_data"] is context.risk_metadata
    assert captured["candles"] == candles
    assert captured["current_price"] == 101.0
    assert captured["current_weight_pct"] == 5.0
    assert captured["marginal_risk_pct"] == 2.0
    assert captured["diversification_benefit_pct"] == 3.0
    assert captured["expected_return_impact_pct"] == 4.0
    assert captured["max_position_weight_pct"] == 10.0
