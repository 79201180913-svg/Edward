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
