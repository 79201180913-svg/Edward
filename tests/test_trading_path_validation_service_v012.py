from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.trading_path_validation_service_v012 import TradingPathValidationServiceV012


def candidate(*, sufficient=True, excess=1.0):
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1", ticker="SBER", hypothesis="BREAKOUT_EXPANSION",
            regime="TREND_UP", volatility_bucket="Normal", direction="Positive", horizon=5,
        ),
        evidence=TradingPathEvidence(
            observations=20, mean_forward_return_pct=1.2, median_forward_return_pct=1.0,
            win_rate_pct=60.0, baseline_mean_return_pct=0.2, excess_return_pct=excess,
            sufficient_sample=sufficient,
        ),
    )


def test_validation_requires_positive_sufficient_path_evidence():
    result = TradingPathValidationServiceV012.validate(candidate())
    assert result.passed is True


def test_validation_rejects_insufficient_or_non_positive_evidence():
    assert TradingPathValidationServiceV012.validate(candidate(sufficient=False)).passed is False
    assert TradingPathValidationServiceV012.validate(candidate(excess=0.0)).passed is False
    assert TradingPathValidationServiceV012.validate(candidate(excess=-1.0)).passed is False


def test_explicit_negative_validation_check_rejects_path():
    result = TradingPathValidationServiceV012.validate(
        candidate(), statistical_valid=True, overlap_valid=True, multiple_testing_valid=False
    )
    assert result.passed is False
    assert result.validation.multiple_testing_valid is False


def test_validation_does_not_create_trade_decision():
    result = TradingPathValidationServiceV012.validate(candidate())
    assert result.candidate.status.value == "research"
