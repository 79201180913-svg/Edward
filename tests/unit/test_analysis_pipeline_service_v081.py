from datetime import datetime, timedelta, timezone

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.analysis_pipeline_service_v081 import AnalysisPipelineServiceV081, AnalysisPipelineV081Result


def _candles(count=320):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        type("CandleLike", (), {
            "timestamp": start + timedelta(days=index),
            "open": 100.0 + index * 0.2,
            "high": 101.0 + index * 0.2,
            "low": 99.0 + index * 0.2,
            "close": 100.0 + index * 0.2,
            "volume": 1000.0,
        })()
        for index in range(count)
    ]


def test_v081_pipeline_wraps_v08_without_replacing_result_contract():
    result = AnalysisPipelineServiceV081().analyze(
        instrument_uid="TQBR.TEST",
        ticker="TEST",
        candles=_candles(),
        session_name="REGULAR",
    )

    assert isinstance(result, AnalysisPipelineV081Result)
    assert isinstance(result.base, AnalysisPipelineV08Result)
    assert result.analysis.instrument_uid == "TQBR.TEST"
    assert result.opportunity is result.base.opportunity
    assert result.expected_value is result.base.expected_value
    assert result.version == "0.8.1"


def test_v081_pipeline_accepts_all_optional_contract_sources():
    result = AnalysisPipelineServiceV081().analyze(
        instrument_uid="TQBR.TEST",
        ticker="TEST",
        candles=_candles(),
        fundamentals={"roe": 18, "roic": 15, "net_margin": 12, "revenue_growth": 10, "eps_growth": 12, "free_cash_flow": 1_000_000, "pe": 10},
        order_book={"bids": [{"price": 99.9, "quantity": 1000}], "asks": [{"price": 100.1, "quantity": 500}]},
        trades=[{"direction": "BUY", "quantity": 200}, {"direction": "SELL", "quantity": 100}],
        current_signal={"direction": "BUY"},
        historical_signals=[{"direction": "BUY", "initial_price": 100, "close_price": 108}] * 10,
        dividend_data={"dividend_yield": 4},
        insider_transactions=[{"type": "BUY", "price": 100, "quantity": 100}],
        session_name="REGULAR",
        risk_data={"dlong_client": 10, "dshort_client": 15, "short_enabled": True},
    )

    assert result.multifactor.fundamentals.evidence.available is True
    assert result.multifactor.microstructure.evidence.available is True
    assert result.multifactor.signals.evidence.available is True
    assert result.multifactor.dividends.evidence.available is True
    assert result.multifactor.insider.evidence.available is True
    assert result.multifactor.instrument_risk.evidence.available is True


def test_v081_normalizes_fractional_risk_rates_and_uses_long_margin_when_short_is_disabled():
    result = AnalysisPipelineServiceV081().analyze(
        instrument_uid="TQBR.RISK",
        ticker="RISK",
        candles=_candles(),
        session_name="REGULAR",
        risk_data={"dlong": 0.25, "dshort": 0.5675, "short_enabled": False},
    )

    risk = result.multifactor.instrument_risk
    assert risk.long_margin_rate_pct == 25.0
    assert risk.short_margin_rate_pct == 56.75
    assert risk.short_enabled is False
    assert risk.capital_efficiency_score == 75.0
    assert risk.risk_score == 83.33333333333333
    assert risk.evidence.available is True


def test_v081_uses_stricter_short_margin_when_short_is_enabled():
    result = AnalysisPipelineServiceV081().analyze(
        instrument_uid="TQBR.RISK_SHORT",
        ticker="RISK_SHORT",
        candles=_candles(),
        session_name="REGULAR",
        risk_data={"dlong": 0.25, "dshort": 0.5675, "short_enabled": True},
    )

    risk = result.multifactor.instrument_risk
    assert risk.long_margin_rate_pct == 25.0
    assert risk.short_margin_rate_pct == 56.75
    assert risk.short_enabled is True
    assert risk.capital_efficiency_score == 43.25
    assert risk.risk_score == 100.0
    assert risk.evidence.available is True
