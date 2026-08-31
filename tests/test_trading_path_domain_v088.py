from edward.domain import (
    TradingPathCandidate,
    TradingPathEvidence,
    TradingPathRule,
    TradingPathStatus,
)


def test_trading_path_candidate_is_research_only_by_default():
    candidate = TradingPathCandidate(
        rule=TradingPathRule("uid-1", "SBER", "BREAKOUT_EXPANSION", "TREND_DOWN", "High", "Positive", 3),
        evidence=TradingPathEvidence(10, 1.2, 1.0, 100.0, 0.2, 1.0, True, 100.0),
    )
    assert candidate.status is TradingPathStatus.RESEARCH
    assert candidate.source_version == "0.8.6"


def test_trading_path_contract_preserves_instrument_and_conditional_dimensions():
    rule = TradingPathRule("uid-2", "GAZP", "PULLBACK_RECLAIM", "TREND_UP", "Normal", "Positive", 5)
    assert (
        rule.instrument_uid, rule.ticker, rule.hypothesis, rule.regime,
        rule.volatility_bucket, rule.direction, rule.horizon,
    ) == ("uid-2", "GAZP", "PULLBACK_RECLAIM", "TREND_UP", "Normal", "Positive", 5)


def test_trading_path_evidence_keeps_low_sample_visible():
    evidence = TradingPathEvidence(1, 22.4, 22.4, 100.0, 0.0, 22.4, False)
    assert evidence.observations == 1
    assert evidence.excess_return_pct == 22.4
    assert evidence.sufficient_sample is False


def test_trading_path_contracts_are_immutable():
    candidate = TradingPathCandidate(
        TradingPathRule("uid-3", "RANGE", "RANGE_BREAK", "TREND_UP", "Low", "Positive", 10),
        TradingPathEvidence(8, 1.0, 0.8, 62.5, 0.2, 0.8, True),
    )
    try:
        candidate.status = TradingPathStatus.VALIDATED
    except AttributeError:
        pass
    else:
        raise AssertionError("TradingPathCandidate must be immutable")
