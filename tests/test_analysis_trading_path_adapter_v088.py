from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088
from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryEvidence, ConditionalDiscoveryResult
from edward.services.analysis_service_v08 import AnalysisV08Diagnostics


@dataclass
class FakeAnalysisService:
    result: AnalysisResult
    last_diagnostics: AnalysisV08Diagnostics | None

    def analyze(self, **kwargs):
        return self.result


def _analysis():
    return AnalysisResult(
        instrument_uid="uid", ticker="SBER", profile="medium_term", risk_profile="balanced", horizon="medium",
        market_regime="TREND_UP", recommendation=None, confidence="Low", score=0.0, strategies=[],
        explanation="test", created_at="2025-01-01T00:00:00+00:00", analysis_version="0.8.7",
    )


def _diagnostics():
    cell = ConditionalDiscoveryCell(
        hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP", volatility_bucket="High", direction="Positive",
        horizon=3, observations=10, mean_forward_return_pct=2.0, median_forward_return_pct=2.0,
        win_rate_pct=70.0, baseline_mean_return_pct=0.5, excess_return_pct=1.5, sufficient_sample=True,
    )
    evidence = ConditionalDiscoveryEvidence(
        hypothesis="BREAKOUT_EXPANSION", events=10, cells=(cell,)
    )
    discovery = ConditionalDiscoveryResult(version="0.8.6", candles=300, min_observations=8, evidence=(evidence,))
    return AnalysisV08Diagnostics(0.9, "TREND_UP", {}, {}, conditional_discovery=discovery)


def _candles():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return tuple(Candle(timestamp=start + timedelta(hours=i), open=100+i, high=101+i, low=99+i, close=100+i, volume=1000) for i in range(300))


def test_adapter_exposes_candidates_without_changing_existing_recommendation():
    service = FakeAnalysisService(_analysis(), _diagnostics())
    result = AnalysisTradingPathAdapterV088(service).analyze(instrument_uid="uid", ticker="SBER", candles=_candles())
    assert result.analysis.recommendation is None
    assert len(result.ranked_candidates) == 1
    assert result.ranked_candidates[0].candidate.status.value == "research"
    assert len(result.overlap_evidence) == 1
    assert result.overlap_evidence[0].compared_candidates == 0
    assert result.overlap_evidence[0].max_event_overlap_ratio == 0.0
    assert result.overlap_evidence[0].max_holding_overlap_ratio == 0.0


def test_adapter_handles_missing_conditional_discovery_without_breaking_analysis():
    service = FakeAnalysisService(_analysis(), AnalysisV08Diagnostics(0.9, "TREND_UP", {}, {}))
    result = AnalysisTradingPathAdapterV088(service).analyze(instrument_uid="uid", ticker="SBER", candles=_candles())
    assert result.ranked_candidates == ()
    assert result.overlap_evidence == ()
    assert result.analysis.recommendation is None
