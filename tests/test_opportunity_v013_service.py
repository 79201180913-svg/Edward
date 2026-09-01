from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012, TradingPathAnalysisStatus, TradingPathCurrentState, TradingPathDecision
from edward.services.opportunity_v013_service import OpportunityV013Service


def _analysis():
    return TradingPathAnalysisV012(
        instrument_uid="SBER", ticker="SBER", strategy_family="H1", hypothesis="H1",
        regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5,
        evidence=SimpleNamespace(), validation=SimpleNamespace(), market_context=SimpleNamespace(),
        opportunity=SimpleNamespace(score=75.0, confidence=80.0),
        current_state=TradingPathCurrentState.ENTRY_READY,
        decision=TradingPathDecision.BUY,
        status=TradingPathAnalysisStatus.PROMOTABLE,
        rank=1,
    )


def test_service_exposes_canonical_analysis_consumer(monkeypatch):
    service = OpportunityV013Service()
    analysis = _analysis()
    called = []

    monkeypatch.setattr(service.runtime, "scan_analyses", lambda analyses: called.append(tuple(analyses)))
    # The facade is intentionally exercised directly through the service's public analysis entry.
    result = service.from_analyses([analysis])

    assert len(result) == 1
    assert result[0].best_path is analysis
    assert result[0].decision is TradingPathDecision.BUY
    assert called == []


def test_service_scan_delegates_to_canonical_runtime():
    class FakeRuntime:
        def scan_instrument(self, **kwargs):
            return "canonical-opportunity"

    service = OpportunityV013Service(runtime=FakeRuntime())
    assert service.scan_instrument(instrument_uid="SBER", ticker="SBER", candles=()) == "canonical-opportunity"
