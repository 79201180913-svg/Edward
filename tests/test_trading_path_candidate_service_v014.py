from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathCandidate, TradingPathRule
from edward.services.conditional_discovery_service_v086 import (
    ConditionalDiscoveryCell,
    ConditionalDiscoveryEvidence,
    ConditionalDiscoveryResult,
)
from edward.services.trading_path_adaptive_discovery_service_v014 import (
    AdaptiveDiscoveryCandidateV014,
    AdaptiveDiscoveryResultV014,
    AdaptiveRuleConditionV014,
    AdaptiveRuleV014,
)
from edward.services.trading_path_candidate_service_v014 import TradingPathCandidateServiceV014


def fixed_result() -> ConditionalDiscoveryResult:
    cell = ConditionalDiscoveryCell(
        hypothesis="BREAKOUT_EXPANSION",
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
        observations=20,
        mean_forward_return_pct=1.5,
        median_forward_return_pct=1.2,
        win_rate_pct=65.0,
        baseline_mean_return_pct=0.5,
        excess_return_pct=1.0,
        sufficient_sample=True,
    )
    return ConditionalDiscoveryResult(
        version="0.8.6",
        candles=100,
        min_observations=8,
        evidence=(ConditionalDiscoveryEvidence(cell.hypothesis, 20, (cell,)),),
    )


def adaptive_result() -> AdaptiveDiscoveryResultV014:
    condition = AdaptiveRuleConditionV014("return_20", ">=", 0.05)
    rule = AdaptiveRuleV014("TREND_UP", 5, (condition,))
    candidate = AdaptiveDiscoveryCandidateV014(
        rule=rule,
        observations=18,
        mean_forward_return_pct=1.8,
        median_forward_return_pct=1.4,
        win_rate_pct=66.7,
        baseline_mean_return_pct=0.5,
        excess_return_pct=1.3,
    )
    return AdaptiveDiscoveryResultV014("0.8.14", 140, 500, (20, 40, 60, 80), (candidate,))


def test_fixed_and_adaptive_share_the_same_candidate_contract():
    fixed = TradingPathCandidateServiceV014.from_fixed(
        fixed_result(), instrument_uid="uid", ticker="TEST",
    )
    adaptive = TradingPathCandidateServiceV014.from_adaptive(
        adaptive_result(), instrument_uid="uid", ticker="TEST",
    )

    assert len(fixed) == 1
    assert len(adaptive) == 1
    assert all(isinstance(item, TradingPathCandidate) for item in fixed + adaptive)
    assert fixed[0].source_version == "fixed:0.8.6"
    assert adaptive[0].source_version == "0.8.14"


def test_adaptive_rule_is_preserved_in_candidate_hypothesis():
    candidates = TradingPathCandidateServiceV014.from_adaptive(
        adaptive_result(), instrument_uid="uid", ticker="TEST",
    )

    candidate = candidates[0]
    assert candidate.rule.hypothesis.startswith("ADAPTIVE_RULE:")
    assert "return_20 >= 0.05" in candidate.rule.hypothesis
    assert candidate.rule.regime == "TREND_UP"
    assert candidate.rule.horizon == 5


def test_combined_layer_keeps_fixed_and_adaptive_candidates():
    fixed = TradingPathCandidateServiceV014.from_fixed(
        fixed_result(), instrument_uid="uid", ticker="TEST",
    )
    adaptive = TradingPathCandidateServiceV014.from_adaptive(
        adaptive_result(), instrument_uid="uid", ticker="TEST",
    )

    combined = TradingPathCandidateServiceV014.combine(fixed, adaptive, ticker="TEST")
    assert len(combined) == 2
    assert {item.source_version for item in combined} == {"fixed:0.8.6", "0.8.14"}


def test_strategy_family_recognizes_adaptive_hypothesis():
    candidate = TradingPathCandidateServiceV014.from_adaptive(
        adaptive_result(), instrument_uid="uid", ticker="TEST",
    )[0]
    assert candidate.rule.hypothesis.startswith("ADAPTIVE_RULE:")


def test_candidate_rule_remains_compatible_with_existing_domain_shape():
    rule = TradingPathRule("uid", "TEST", "BREAKOUT_EXPANSION", "TREND_UP", "Normal", "Positive", 5)
    assert rule.horizon == 5
    assert rule.ticker == "TEST"
