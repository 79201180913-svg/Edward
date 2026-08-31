from edward.domain import (
    TradingPathCandidate,
    TradingPathEvidence,
    TradingPathRule,
    TradingPathStatus,
)


def test_trading_path_candidate_is_research_only_by_default():
    candidate = TradingPathCandidate(
        rule=TradingPathRule(
            hypothesis="BREAKOUT_EXPANSION",
            regime="TREND_DOWN",
            volatility_bucket="High",
            direction="Positive",
            horizon=3,
        ),
        evidence=TradingPathEvidence(
            observations=10,
            mean_forward_return_pct=1.2,
            median_forward_return_pct=1.0,
            win_rate_pct=100.0,
            baseline_mean_return_pct=0.2,
            excess_return_pct=1.0,
            sufficient_sample=True,
            wf_persistence_pct=100.0,
        ),
    )

    assert candidate.status is TradingPathStatus.RESEARCH
    assert candidate.source_version == "0.8.6"


def test_trading_path_contract_preserves_conditional_dimensions():
    rule = TradingPathRule(
        hypothesis="PULLBACK_RECLAIM",
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
    )

    assert (
        rule.hypothesis,
        rule.regime,
        rule.volatility_bucket,
        rule.direction,
        rule.horizon,
    ) == ("PULLBACK_RECLAIM", "TREND_UP", "Normal", "Positive", 5)


def test_trading_path_evidence_keeps_low_sample_visible():
    evidence = TradingPathEvidence(
        observations=1,
        mean_forward_return_pct=22.4,
        median_forward_return_pct=22.4,
        win_rate_pct=100.0,
        baseline_mean_return_pct=0.0,
        excess_return_pct=22.4,
        sufficient_sample=False,
    )

    assert evidence.observations == 1
    assert evidence.excess_return_pct == 22.4
    assert evidence.sufficient_sample is False


def test_trading_path_contracts_are_immutable():
    candidate = TradingPathCandidate(
        rule=TradingPathRule("RANGE_BREAK", "TREND_UP", "Low", "Positive", 10),
        evidence=TradingPathEvidence(8, 1.0, 0.8, 62.5, 0.2, 0.8, True),
    )

    try:
        candidate.status = TradingPathStatus.VALIDATED
    except AttributeError:
        pass
    else:
        raise AssertionError("TradingPathCandidate must be immutable")
