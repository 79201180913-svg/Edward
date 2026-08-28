from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisServiceV082
from edward.services.multifactor_analysis_service_v081 import MultiFactorAnalysisServiceV081


def test_v081_fundamentals_delegates_to_v082_for_mapped_snapshot():
    snapshot = {
        "roe": 20.0,
        "roic": 15.0,
        "roa": 8.0,
        "net_margin": 12.0,
        "revenue_growth": 10.0,
        "revenue_growth_3y": 8.0,
        "revenue_growth_5y": 6.0,
        "eps_growth": 12.0,
        "ebitda_growth": 9.0,
        "current_ratio": 1.5,
        "net_debt_to_ebitda": 1.0,
        "free_cash_flow": 100.0,
        "free_cash_flow_to_price": 5.0,
        "pe": 10.0,
        "ps": 2.0,
        "pb": 2.0,
        "p_fcf": 12.0,
        "ev_to_ebitda": 8.0,
        "ev_to_sales": 2.0,
        "dividend_yield": 5.0,
        "dividend_payout": 40.0,
        "dividend_growth": 5.0,
        "dividend_regularity": 100.0,
    }
    factor = MultiFactorAnalysisServiceV081.fundamentals(snapshot)
    canonical = FundamentalAnalysisServiceV082.analyze(snapshot)

    assert factor.evidence.available is True
    assert factor.evidence.reason is None
    assert factor.evidence.strength == canonical.overall_score
    assert factor.quality_score == canonical.business_quality.score
    assert factor.growth_score == canonical.growth.score
    assert factor.valuation_score == canonical.valuation.score


def test_v081_fundamentals_keeps_unavailable_semantics():
    factor = MultiFactorAnalysisServiceV081.fundamentals(None)
    assert factor.evidence.available is False
    assert factor.evidence.reason == "NO_FUNDAMENTAL_DATA"
