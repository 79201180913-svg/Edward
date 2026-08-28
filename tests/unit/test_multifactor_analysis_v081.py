from datetime import datetime, timedelta, timezone

from edward.services.multifactor_analysis_service_v081 import MultiFactorAnalysisServiceV081


def test_missing_optional_sources_are_unavailable_not_zero_evidence():
    result = MultiFactorAnalysisServiceV081.analyze()

    assert result.fundamentals.evidence.available is False
    assert result.microstructure.evidence.available is False
    assert result.volume_pressure.evidence.available is False
    assert result.signals.evidence.available is False
    assert result.event_risk.evidence.available is False
    assert result.dividends.evidence.available is False
    assert result.insider.evidence.available is False
    assert result.instrument_risk.evidence.available is False


def test_fundamental_quality_rewards_profitability_growth_and_cash_flow():
    factor = MultiFactorAnalysisServiceV081.fundamentals(
        {
            "roe": 18,
            "roic": 16,
            "net_margin": 12,
            "revenue_growth": 10,
            "eps_growth": 15,
            "ebitda_growth": 11,
            "net_debt_to_ebitda": 1.0,
            "current_ratio": 1.8,
            "free_cash_flow": 20_000_000,
            "pe": 10,
            "ps": 2,
            "pb": 2,
            "p_fcf": 12,
            "dividend_yield": 4,
            "dividend_payout": 35,
        }
    )

    assert factor.quality_score > 60
    assert factor.growth_score > 60
    assert factor.cash_flow_score > 50
    assert factor.evidence.direction == "POSITIVE"


def test_fundamental_growth_uses_contract_three_and_five_year_revenue_metrics():
    without_long_term = MultiFactorAnalysisServiceV081.fundamentals(
        {
            "revenue_growth": 0,
            "eps_growth": 0,
            "ebitda_growth": 0,
        }
    )
    with_long_term = MultiFactorAnalysisServiceV081.fundamentals(
        {
            "revenue_growth": 0,
            "revenue_growth_3y": 20,
            "revenue_growth_5y": 30,
            "eps_growth": 0,
            "ebitda_growth": 0,
        }
    )

    assert with_long_term.growth_score > without_long_term.growth_score


def test_microstructure_penalizes_wide_spread_and_rewards_liquidity():
    good = MultiFactorAnalysisServiceV081.microstructure(
        {
            "bids": [{"price": 99.9, "quantity": 1000}, {"price": 99.8, "quantity": 1000}],
            "asks": [{"price": 100.1, "quantity": 500}, {"price": 100.2, "quantity": 500}],
        },
        [{"direction": "BUY", "quantity": 800}, {"direction": "SELL", "quantity": 200}],
        100,
    )
    bad = MultiFactorAnalysisServiceV081.microstructure(
        {
            "bids": [{"price": 95, "quantity": 100}],
            "asks": [{"price": 105, "quantity": 100}],
        },
        [{"direction": "SELL", "quantity": 1000}],
        100,
    )

    assert good.spread_pct < bad.spread_pct
    assert good.entry_quality_score > bad.entry_quality_score


def test_volume_pressure_detects_accumulation():
    candles = [
        {"volume": 100, "volume_buy": 80, "volume_sell": 20},
        {"volume": 100, "volume_buy": 70, "volume_sell": 30},
    ]

    factor = MultiFactorAnalysisServiceV081.volume_pressure(candles)

    assert factor.buy_pressure_pct > factor.sell_pressure_pct
    assert factor.accumulation_score > factor.distribution_score
    assert factor.evidence.direction == "POSITIVE"


def test_signal_reliability_requires_historical_evidence():
    factor = MultiFactorAnalysisServiceV081.signals(
        {"direction": "BUY"},
        [
            {"direction": "BUY", "initial_price": 100, "close_price": 110},
            {"direction": "BUY", "initial_price": 100, "close_price": 105},
            {"direction": "BUY", "initial_price": 100, "close_price": 95},
        ],
    )

    assert factor.current_direction == "BUY"
    assert factor.historical_hit_rate_pct == 2 / 3 * 100
    assert factor.reliability_pct > 40


def test_event_risk_rises_close_to_report_date():
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    near = MultiFactorAnalysisServiceV081.event_risk({"report_date": now + timedelta(days=2)}, now=now)
    far = MultiFactorAnalysisServiceV081.event_risk({"report_date": now + timedelta(days=60)}, now=now)

    assert near.event_risk_score > far.event_risk_score
    assert near.evidence.direction == "NEGATIVE"


def test_dividend_factor_uses_yield_growth_and_payout():
    factor = MultiFactorAnalysisServiceV081.dividends({"dividend_yield": 6, "dividend_payout": 40, "dividend_growth": 8, "dividend_regularity": 80})

    assert factor.yield_pct == 6
    assert factor.growth_score > 50
    assert factor.stability_score > 50
    assert factor.evidence.direction == "POSITIVE"


def test_insider_factor_aggregates_net_buying_and_selling():
    factor = MultiFactorAnalysisServiceV081.insiders(
        [
            {"type": "BUY", "quantity": 100},
            {"type": "BUY", "quantity": 50},
            {"type": "SELL", "quantity": 25},
        ]
    )

    assert factor.net_direction == "BUY"
    assert factor.activity_score > 50
    assert factor.evidence.direction == "POSITIVE"


def test_clearing_session_blocks_execution():
    factor = MultiFactorAnalysisServiceV081.session("CLEARING", execution_allowed=True)

    assert factor.is_execution_allowed is False
    assert factor.quality_score == 0


def test_instrument_risk_penalizes_high_margin_rates():
    factor = MultiFactorAnalysisServiceV081.instrument_risk({"dlong_client": 25, "dshort_client": 35, "short_enabled": True})

    assert factor.short_enabled is True
    assert factor.risk_score > 50
    assert factor.evidence.direction == "NEGATIVE"


def test_portfolio_factor_penalizes_high_current_weight_and_marginal_risk():
    low = MultiFactorAnalysisServiceV081.portfolio(current_weight_pct=2, marginal_risk_pct=0.5, diversification_benefit_pct=3, max_position_weight_pct=10)
    high = MultiFactorAnalysisServiceV081.portfolio(current_weight_pct=12, marginal_risk_pct=3, diversification_benefit_pct=-1, max_position_weight_pct=10)

    assert low.concentration_score > high.concentration_score
    assert low.evidence.quality > high.evidence.quality


def test_aggregate_evidence_penalizes_conflicting_sources():
    positive = MultiFactorAnalysisServiceV081.fundamentals(
        {"roe": 20, "roic": 20, "net_margin": 15, "revenue_growth": 15, "eps_growth": 15, "ebitda_growth": 15, "net_debt_to_ebitda": 0.5, "current_ratio": 2, "free_cash_flow": 20_000_000, "pe": 8}
    )
    signal = MultiFactorAnalysisServiceV081.signals({"direction": "SELL"}, [{"direction": "SELL", "initial_price": 100, "close_price": 90}] * 20)

    score, reliability, conflict = MultiFactorAnalysisServiceV081.aggregate([positive.evidence, signal.evidence])

    assert score >= 0
    assert reliability > 0
    assert conflict > 0


def test_multifactor_result_excludes_analyst_consensus_as_a_source():
    result = MultiFactorAnalysisServiceV081.analyze(fundamentals={"roe": 10})

    evidence_names = {
        result.fundamentals.evidence.name,
        result.microstructure.evidence.name,
        result.volume_pressure.evidence.name,
        result.signals.evidence.name,
        result.event_risk.evidence.name,
        result.dividends.evidence.name,
        result.insider.evidence.name,
        result.session.evidence.name,
        result.instrument_risk.evidence.name,
        result.portfolio.evidence.name,
    }
    assert "analyst_consensus" not in evidence_names
