from edward.services.fundamental_analysis_service_v082 import FUNDAMENTAL_ANALYSIS_VERSION, FundamentalAnalysisServiceV082


def test_version_is_082():
    assert FUNDAMENTAL_ANALYSIS_VERSION == "0.8.2"


def test_missing_fundamentals_are_unavailable():
    result = FundamentalAnalysisServiceV082.analyze(None)
    assert result.status == "UNAVAILABLE"
    assert result.overall_score == 0.0
    assert result.confidence == 0.0
    assert result.coverage == 0.0
    assert "NO_FUNDAMENTAL_DATA" in result.reason_codes


def test_full_snapshot_produces_all_groups():
    snapshot = {
        "roe": 25.0, "roic": 22.0, "roa": 12.0, "net_margin": 14.0,
        "revenue_growth": 18.0, "revenue_growth_3y": 14.0, "revenue_growth_5y": 10.0,
        "revenue_change_5y": 45.0, "eps_growth": 20.0, "ebitda_growth": 17.0,
        "net_debt_to_ebitda": 1.0, "total_debt_to_ebitda": 1.2, "total_debt_to_equity": 0.4,
        "current_ratio": 1.8, "free_cash_flow": 1000000.0, "free_cash_flow_to_price": 7.0,
        "pe": 14.0, "ps": 2.0, "pb": 2.5, "p_fcf": 12.0, "ev_to_ebitda": 10.0,
        "ev_to_sales": 2.0, "dividend_yield": 4.0, "dividend_payout": 45.0,
        "dividend_growth": 8.0, "dividend_regularity": 100.0,
    }
    result = FundamentalAnalysisServiceV082.analyze(snapshot)
    assert result.status == "AVAILABLE"
    assert result.coverage == 100.0
    assert result.confidence == 100.0
    assert result.overall_score > 0
    assert result.fundamental_momentum.coverage == 100.0


def test_partial_data_reduces_coverage_and_confidence():
    result = FundamentalAnalysisServiceV082.analyze({"roe": 30.0, "roic": 25.0, "revenue_growth": 20.0})
    assert result.status == "PARTIAL"
    assert 0.0 < result.coverage < 100.0
    assert 0.0 < result.confidence < 100.0
    assert result.business_quality.score > 0.0
    assert result.business_quality.coverage == 50.0
    assert "PARTIAL_DATA_COVERAGE" in result.business_quality.reason_codes


def test_growth_acceleration_is_exposed():
    result = FundamentalAnalysisServiceV082.analyze({
        "revenue_growth_5y": 5.0, "revenue_growth_3y": 10.0,
        "revenue_growth": 20.0, "eps_growth": 15.0, "ebitda_growth": 18.0,
    })
    assert result.fundamental_momentum.score > 50.0
    assert "FUNDAMENTAL_ACCELERATION" in result.fundamental_momentum.reason_codes


def test_input_is_not_mutated():
    snapshot = {"roe": 20.0, "revenue_growth": 10.0}
    original = dict(snapshot)
    FundamentalAnalysisServiceV082.analyze(snapshot)
    assert snapshot == original


def test_strategy_profile_is_exposed_and_weights_are_normalized():
    snapshot = {"roe": 20.0, "revenue_growth": 10.0, "pe": 20.0}
    result = FundamentalAnalysisServiceV082.analyze(snapshot, profile="long_term")
    assert result.strategy_profile == "long_term"
    assert result.group_weights
    assert abs(sum(weight for _, weight in result.group_weights) - 1.0) < 1e-9


def test_long_term_and_speculative_profiles_weight_fundamentals_differently():
    snapshot = {
        "roe": 20.0, "roic": 20.0, "roa": 10.0, "net_margin": 12.0,
        "revenue_growth": 30.0, "revenue_growth_3y": 15.0, "revenue_growth_5y": 5.0,
        "eps_growth": 25.0, "ebitda_growth": 20.0,
        "current_ratio": 1.5, "net_debt_to_ebitda": 1.0,
        "free_cash_flow": 100.0, "free_cash_flow_to_price": 4.0,
        "pe": 20.0, "ps": 3.0, "pb": 3.0, "p_fcf": 18.0,
        "ev_to_ebitda": 14.0, "ev_to_sales": 3.0,
        "dividend_yield": 2.0, "dividend_payout": 40.0,
        "dividend_growth": 5.0, "dividend_regularity": 100.0,
    }
    long_term = FundamentalAnalysisServiceV082.analyze(snapshot, profile="long_term")
    speculative = FundamentalAnalysisServiceV082.analyze(snapshot, profile="speculative")
    long_weights = dict(long_term.group_weights)
    speculative_weights = dict(speculative.group_weights)
    assert long_weights["business_quality"] > speculative_weights["business_quality"]
    assert speculative_weights["fundamental_momentum"] > long_weights["fundamental_momentum"]
    assert long_term.overall_score != speculative.overall_score


def test_missing_weighted_group_is_renormalized_not_treated_as_zero_score():
    snapshot = {"roe": 25.0, "roic": 22.0, "roa": 12.0, "net_margin": 14.0}
    result = FundamentalAnalysisServiceV082.analyze(snapshot, profile="long_term")
    weights = dict(result.group_weights)
    assert "business_quality" in weights
    assert "valuation" not in weights
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert result.overall_score > 50.0


def test_profile_aliases_are_supported():
    result = FundamentalAnalysisServiceV082.analyze({"roe": 20.0}, profile="long-term")
    assert result.strategy_profile == "long_term"


def test_explicit_not_applicable_metric_is_excluded_from_group_score_and_coverage():
    result = FundamentalAnalysisServiceV082.analyze({
        "roe": 30.0,
        "roic": 0.0,
        "roa": 5.0,
        "net_margin": 10.0,
        "__not_applicable_metrics": ["roic"],
    })
    assert result.business_quality.coverage == 100.0
    assert result.business_quality.score == (
        FundamentalAnalysisServiceV082._metric_score("roe", 30.0)
        + FundamentalAnalysisServiceV082._metric_score("roa", 5.0)
        + FundamentalAnalysisServiceV082._metric_score("net_margin", 10.0)
    ) / 3
    roic = next(metric for metric in result.business_quality.metrics if metric.metric == "roic")
    assert roic.available is False
    assert roic.value is None
    assert "METRIC_NOT_APPLICABLE" in roic.reason_codes


def test_bank_context_marks_bank_specific_metrics_not_applicable_even_when_zero():
    result = FundamentalAnalysisServiceV082.analyze({
        "roe": 23.0,
        "roic": 0.0,
        "roa": 2.8,
        "net_margin": 0.0,
        "ebitda_growth": 0.0,
        "net_debt_to_ebitda": 0.0,
        "total_debt_to_ebitda": 0.0,
        "current_ratio": 0.0,
        "ev_to_ebitda": 0.0,
        "ev_to_sales": 0.0,
        "__instrument_context": {"sector": "Banks"},
    })
    for group_name, metric_names in {
        "business_quality": {"roic"},
        "growth": {"ebitda_growth"},
        "financial_health": {"net_debt_to_ebitda", "total_debt_to_ebitda", "current_ratio"},
        "valuation": {"ev_to_ebitda", "ev_to_sales"},
        "fundamental_momentum": {"ebitda_growth"},
    }.items():
        metrics = {metric.metric: metric for metric in getattr(result, group_name).metrics}
        for name in metric_names:
            assert metrics[name].available is False
            assert "METRIC_NOT_APPLICABLE" in metrics[name].reason_codes


def test_zero_is_still_a_valid_value_without_non_applicable_context():
    result = FundamentalAnalysisServiceV082.analyze({"roe": 0.0})
    metric = next(item for item in result.business_quality.metrics if item.metric == "roe")
    assert metric.available is True
    assert metric.value == 0.0


def test_cumulative_revenue_change_is_visible_but_excluded_from_growth_score():
    base = {
        "revenue_growth": 25.2,
        "revenue_growth_3y": 33.0,
        "eps_growth": 126.9,
    }
    low_cumulative = FundamentalAnalysisServiceV082.analyze(
        {**base, "revenue_change_5y": 10.0}
    )
    high_cumulative = FundamentalAnalysisServiceV082.analyze(
        {**base, "revenue_change_5y": 999.0}
    )

    assert low_cumulative.growth.score == high_cumulative.growth.score
    assert low_cumulative.growth.coverage == 60.0
    assert "EVIDENCE_METRICS_EXCLUDED_FROM_SCORE" in low_cumulative.growth.reason_codes
    cumulative = next(
        metric for metric in low_cumulative.growth.metrics if metric.metric == "revenue_change_5y"
    )
    assert cumulative.available is True
    assert cumulative.value == 10.0


def test_growth_score_uses_only_normalized_growth_and_earnings_metrics():
    result = FundamentalAnalysisServiceV082.analyze({
        "revenue_growth": 25.2,
        "revenue_growth_3y": 33.0,
        "revenue_change_5y": 242.2,
        "eps_growth": 126.9,
    })
    expected = (
        FundamentalAnalysisServiceV082._metric_score("revenue_growth", 25.2)
        + FundamentalAnalysisServiceV082._metric_score("revenue_growth_3y", 33.0)
        + FundamentalAnalysisServiceV082._metric_score("eps_growth", 126.9)
    ) / 3
    assert result.growth.score == expected
    assert result.growth.coverage == 60.0
