from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.trading_path_ranking_service_v012 import TradingPathRankingServiceV012


def _candidate(*, hypothesis: str, excess: float, win_rate: float, median: float, observations: int) -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1",
            ticker="SBER",
            hypothesis=hypothesis,
            regime="TREND_UP",
            volatility_bucket="Normal",
            direction="Positive",
            horizon=5,
        ),
        evidence=TradingPathEvidence(
            observations=observations,
            mean_forward_return_pct=excess + 0.2,
            median_forward_return_pct=median,
            win_rate_pct=win_rate,
            baseline_mean_return_pct=0.2,
            excess_return_pct=excess,
            sufficient_sample=True,
        ),
    )


def test_ranking_prefers_excess_return_then_secondary_evidence():
    candidates = (
        _candidate(hypothesis="BREAKOUT_EXPANSION", excess=1.0, win_rate=60.0, median=0.7, observations=20),
        _candidate(hypothesis="GAP_REVERSAL", excess=2.0, win_rate=50.0, median=0.5, observations=10),
        _candidate(hypothesis="IMPULSE_CONTINUATION", excess=1.0, win_rate=70.0, median=0.6, observations=30),
    )

    ranked = TradingPathRankingServiceV012.rank(candidates)

    assert [item.hypothesis for item in ranked] == [
        "GAP_REVERSAL",
        "IMPULSE_CONTINUATION",
        "BREAKOUT_EXPANSION",
    ]
    assert [item.rank for item in ranked] == [1, 2, 3]


def test_ranking_maps_hypothesis_to_strategy_family():
    ranked = TradingPathRankingServiceV012.rank(
        [_candidate(hypothesis="BREAKOUT_EXPANSION", excess=1.0, win_rate=60.0, median=0.7, observations=20)]
    )

    assert ranked[0].strategy_family == "Breakout"


def test_ranking_never_creates_trade_signal():
    ranked = TradingPathRankingServiceV012.rank(
        [_candidate(hypothesis="GAP_REVERSAL", excess=5.0, win_rate=90.0, median=4.0, observations=100)]
    )

    assert ranked[0].decision.value == "wait"
    assert ranked[0].current_state.value == "wait"
    assert ranked[0].status.value == "discovered"
    assert ranked[0].opportunity.score is None


def test_unknown_hypothesis_is_excluded_from_canonical_analysis():
    ranked = TradingPathRankingServiceV012.rank(
        [_candidate(hypothesis="UNKNOWN_HYPOTHESIS", excess=5.0, win_rate=90.0, median=4.0, observations=100)]
    )

    assert ranked == ()
