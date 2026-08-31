from edward.services.conditional_discovery_service_v086 import (
    ConditionalDiscoveryCell,
    ConditionalDiscoveryEvidence,
    ConditionalDiscoveryResult,
)
from edward.services.trading_path_candidate_service_v088 import TradingPathCandidateServiceV088


def _cell(*, sufficient: bool, excess: float = 1.0) -> ConditionalDiscoveryCell:
    return ConditionalDiscoveryCell(
        hypothesis="BREAKOUT_EXPANSION",
        regime="TREND_DOWN",
        volatility_bucket="High",
        direction="Positive",
        horizon=3,
        observations=10 if sufficient else 2,
        mean_forward_return_pct=1.2,
        median_forward_return_pct=1.0,
        win_rate_pct=70.0,
        baseline_mean_return_pct=0.2,
        excess_return_pct=excess,
        sufficient_sample=sufficient,
    )


def test_promotes_only_sufficient_cells():
    result = ConditionalDiscoveryResult(
        version="0.8.6",
        candles=1768,
        min_observations=8,
        evidence=(
            ConditionalDiscoveryEvidence(
                hypothesis="BREAKOUT_EXPANSION",
                events=12,
                cells=(_cell(sufficient=True), _cell(sufficient=False, excess=22.4)),
            ),
        ),
    )

    candidates = TradingPathCandidateServiceV088.promote(result)

    assert len(candidates) == 1
    assert candidates[0].status.value == "research"
    assert candidates[0].evidence.observations == 10


def test_promotion_preserves_all_conditional_dimensions():
    result = ConditionalDiscoveryResult(
        version="0.8.6",
        candles=500,
        min_observations=8,
        evidence=(
            ConditionalDiscoveryEvidence("GAP_REVERSAL", 9, (_cell(sufficient=True),)),
        ),
    )

    candidate = TradingPathCandidateServiceV088.promote(result)[0]

    assert candidate.rule.hypothesis == "BREAKOUT_EXPANSION"
    assert candidate.rule.regime == "TREND_DOWN"
    assert candidate.rule.volatility_bucket == "High"
    assert candidate.rule.direction == "Positive"
    assert candidate.rule.horizon == 3


def test_promotion_does_not_turn_positive_excess_into_trade_status():
    result = ConditionalDiscoveryResult(
        version="0.8.6",
        candles=500,
        min_observations=8,
        evidence=(
            ConditionalDiscoveryEvidence("BREAKOUT_EXPANSION", 10, (_cell(sufficient=True, excess=5.0),)),
        ),
    )

    candidate = TradingPathCandidateServiceV088.promote(result)[0]

    assert candidate.status.value == "research"
    assert candidate.evidence.excess_return_pct == 5.0
