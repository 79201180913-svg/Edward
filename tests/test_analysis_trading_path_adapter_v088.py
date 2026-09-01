from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088
from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryCell, ConditionalDiscoveryEvidence, ConditionalDiscoveryResult
from edward.services.analysis_service_v08 import AnalysisV08Diagnostics
from edward.services.market_context_shadow_scoring_v011 import MarketContextShadowScoreV011


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


def test_market_context_order_reorders_research_bundle_together():
    first = object()
    second = object()
    first_shadow = MarketContextShadowScoreV011(
        baseline_score=10.0,
        context_adjusted_score=8.0,
        score_delta=-2.0,
        baseline_rank=1,
        context_rank=2,
        rank_delta=-1,
        regime_compatibility=20.0,
        relative_strength_component=0.0,
        volatility_component=0.0,
        confidence_hint_delta=-1.0,
    )
    second_shadow = MarketContextShadowScoreV011(
        baseline_score=9.0,
        context_adjusted_score=12.0,
        score_delta=3.0,
        baseline_rank=2,
        context_rank=1,
        rank_delta=1,
        regime_compatibility=100.0,
        relative_strength_component=1.0,
        volatility_component=1.0,
        confidence_hint_delta=1.5,
    )
    ordered = AnalysisTradingPathAdapterV088._apply_market_context_order(
        (first, second),
        ("validation-1", "validation-2"),
        ("overlap-1", "overlap-2"),
        ("multiple-1", "multiple-2"),
        ("promotion-1", "promotion-2"),
        ((first, first_shadow), (second, second_shadow)),
    )
    assert ordered[0] == (second, first)
    assert ordered[1] == ("validation-2", "validation-1")
    assert ordered[2] == ("overlap-2", "overlap-1")
    assert ordered[3] == ("multiple-2", "multiple-1")
    assert ordered[4] == ("promotion-2", "promotion-1")


def test_adapter_handles_missing_conditional_discovery_without_breaking_analysis():
    service = FakeAnalysisService(_analysis(), AnalysisV08Diagnostics(0.9, "TREND_UP", {}, {}))
    result = AnalysisTradingPathAdapterV088(service).analyze(instrument_uid="uid", ticker="SBER", candles=_candles())
    assert result.ranked_candidates == ()
    assert result.overlap_evidence == ()
    assert result.analysis.recommendation is None
