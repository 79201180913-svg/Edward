from edward.services.trading_path_multiple_testing_v088 import TradingPathMultipleTestingServiceV088


def test_bonferroni_adjustment_uses_full_candidate_family():
    evidence = TradingPathMultipleTestingServiceV088.evaluate(
        mean_return_pct=2.0,
        standard_error_pct=0.2,
        tests_count=28,
    )
    assert evidence.tests_count == 28
    assert evidence.adjusted_alpha == 0.05 / 28
    assert evidence.adjusted_ci95_low_pct < 2.0
    assert evidence.adjusted_ci95_high_pct > 2.0


def test_single_test_matches_family_alpha():
    evidence = TradingPathMultipleTestingServiceV088.evaluate(
        mean_return_pct=2.0,
        standard_error_pct=0.0,
        tests_count=1,
    )
    assert evidence.adjusted_alpha == 0.05
    assert evidence.adjusted_ci95_low_pct == 2.0
    assert evidence.passes is True


def test_multiple_testing_can_reject_nominally_positive_path():
    evidence = TradingPathMultipleTestingServiceV088.evaluate(
        mean_return_pct=0.5,
        standard_error_pct=0.3,
        tests_count=28,
    )
    assert evidence.passes is False
