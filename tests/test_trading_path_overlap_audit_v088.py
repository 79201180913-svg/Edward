from types import SimpleNamespace

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.trading_path_overlap_audit_v088 import TradingPathOverlapAuditV088


def _candidate(hypothesis: str, horizon: int = 3):
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid", ticker="SBER", hypothesis=hypothesis,
            regime="TREND_UP", volatility_bucket="High", direction="Positive", horizon=horizon,
        ),
        evidence=TradingPathEvidence(
            observations=3, mean_forward_return_pct=2.0, median_forward_return_pct=2.0,
            win_rate_pct=66.0, baseline_mean_return_pct=0.5, excess_return_pct=1.5, sufficient_sample=True,
        ),
    )


def _obs(hypothesis: str, index: int):
    return SimpleNamespace(
        hypothesis=hypothesis, regime="TREND_UP", volatility_bucket="High", direction="Positive", index=index,
    )


def test_event_overlap_uses_shared_event_indices():
    first = _candidate("BREAKOUT_EXPANSION")
    second = _candidate("IMPULSE_CONTINUATION")
    evidence = TradingPathOverlapAuditV088.audit(
        first, (first, second),
        (_obs("BREAKOUT_EXPANSION", 1), _obs("BREAKOUT_EXPANSION", 2), _obs("IMPULSE_CONTINUATION", 2), _obs("IMPULSE_CONTINUATION", 3)),
    )
    assert evidence.max_event_overlap_ratio == 0.5
    assert evidence.overlap_detected is True


def test_holding_overlap_detects_shared_windows_even_when_events_differ():
    first = _candidate("BREAKOUT_EXPANSION", horizon=3)
    second = _candidate("IMPULSE_CONTINUATION", horizon=3)
    evidence = TradingPathOverlapAuditV088.audit(
        first, (first, second),
        (_obs("BREAKOUT_EXPANSION", 10), _obs("IMPULSE_CONTINUATION", 12)),
    )
    assert evidence.max_event_overlap_ratio == 0.0
    assert evidence.max_holding_overlap_ratio > 0.0


def test_no_overlap_when_paths_have_disjoint_events_and_windows():
    first = _candidate("BREAKOUT_EXPANSION", horizon=2)
    second = _candidate("IMPULSE_CONTINUATION", horizon=2)
    evidence = TradingPathOverlapAuditV088.audit(
        first, (first, second),
        (_obs("BREAKOUT_EXPANSION", 1), _obs("IMPULSE_CONTINUATION", 10)),
    )
    assert evidence.max_event_overlap_ratio == 0.0
    assert evidence.max_holding_overlap_ratio == 0.0
