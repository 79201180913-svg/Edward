from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.trading_path_ranking_v088 import TradingPathRankingServiceV088


def _candidate(excess: float, observations: int = 10, horizon: int = 3) -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule("uid", "SBER", "BREAKOUT_EXPANSION", "TREND_DOWN", "High", "Positive", horizon),
        evidence=TradingPathEvidence(observations, excess + 0.2, excess, 70.0, 0.2, excess, True, 80.0),
    )


def test_ranking_is_descending_and_deterministic():
    ranked = TradingPathRankingServiceV088.rank_and_deduplicate((_candidate(1.0, 10, 3), _candidate(2.0, 10, 5)))
    assert [item.candidate.rule.horizon for item in ranked] == [5, 3]
    assert ranked[0].score > ranked[1].score


def test_duplicate_rule_keeps_highest_scoring_candidate():
    ranked = TradingPathRankingServiceV088.rank_and_deduplicate((_candidate(1.0, 8), _candidate(2.0, 20)))
    assert len(ranked) == 1
    assert ranked[0].candidate.evidence.excess_return_pct == 2.0


def test_ranking_does_not_promote_candidate_to_trade():
    ranked = TradingPathRankingServiceV088.rank_and_deduplicate((_candidate(5.0),))
    assert ranked[0].candidate.status.value == "research"
