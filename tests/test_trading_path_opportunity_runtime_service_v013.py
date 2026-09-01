from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012, TradingPathDecision, TradingPathCurrentState, TradingPathAnalysisStatus
from edward.services.trading_path_opportunity_runtime_service_v013 import TradingPathOpportunityRuntimeServiceV013


def _analysis(rank=1):
    return TradingPathAnalysisV012(
        instrument_uid="SBER", ticker="SBER", strategy_family="H1", hypothesis="H1",
        regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5,
        evidence=SimpleNamespace(), validation=SimpleNamespace(), market_context=SimpleNamespace(),
        opportunity=SimpleNamespace(score=75.0, confidence=80.0),
        current_state=TradingPathCurrentState.ENTRY_READY,
        decision=TradingPathDecision.BUY,
        status=TradingPathAnalysisStatus.PROMOTABLE,
        rank=rank,
    )


def test_scan_analyses_uses_canonical_consumer():
    runtime = TradingPathOpportunityRuntimeServiceV013()
    result = runtime.scan_analyses([_analysis()])

    assert len(result) == 1
    assert result[0].instrument_uid == "SBER"
    assert result[0].best_path.hypothesis == "H1"
    assert result[0].decision is TradingPathDecision.BUY


def test_scan_instrument_delegates_analysis_and_does_not_run_legacy_engine(monkeypatch):
    expected = (_analysis(),)

    class FakeRuntime:
        def analyze_paths(self, **kwargs):
            return expected

    runtime = TradingPathOpportunityRuntimeServiceV013(analysis_runtime=FakeRuntime())
    result = runtime.scan_instrument(instrument_uid="SBER", ticker="SBER", candles=())

    assert result is not None
    assert result.best_path is expected[0]
