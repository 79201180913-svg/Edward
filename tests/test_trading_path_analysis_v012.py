from edward.domain import TradingPathValidationSummary


def test_validation_summary_exposes_statistical_integrity_snapshot():
    summary = TradingPathValidationSummary(
        statistical_valid=True,
        overlap_valid=True,
        multiple_testing_valid=True,
        effective_sample_size=12.5,
        overlap_ratio_pct=80.0,
        standard_error_pct=0.2,
        z_score=2.5,
        p_value_one_sided=0.0062,
        adjusted_p_value=0.0372,
        hypotheses_tested=6,
    )

    assert summary.statistical_valid is True
    assert summary.overlap_valid is True
    assert summary.multiple_testing_valid is True
    assert summary.effective_sample_size == 12.5
    assert summary.overlap_ratio_pct == 80.0
    assert summary.standard_error_pct == 0.2
    assert summary.z_score == 2.5
    assert summary.p_value_one_sided == 0.0062
    assert summary.adjusted_p_value == 0.0372
    assert summary.hypotheses_tested == 6
