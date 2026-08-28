from datetime import datetime, timedelta, timezone

from edward.services.analysis_pipeline_service_v081 import AnalysisPipelineServiceV081


def _candles(count=100):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        type("CandleLike", (), {
            "timestamp": start + timedelta(days=i),
            "open": 100.0 + i * 0.1,
            "high": 101.0 + i * 0.1,
            "low": 99.0 + i * 0.1,
            "close": 100.0 + i * 0.1,
            "volume": 1000.0,
        })()
        for i in range(count)
    ]


def test_absent_portfolio_and_session_context_do_not_become_fake_neutral_evidence():
    result = AnalysisPipelineServiceV081().analyze(
        instrument_uid="TQBR.TEST",
        ticker="TEST",
        candles=_candles(),
    )

    assert result.multifactor.portfolio.evidence.available is False
    assert result.multifactor.session.evidence.available is False
    assert result.multifactor.portfolio.evidence.reason == "NO_PORTFOLIO_CONTEXT"
    assert result.multifactor.session.evidence.reason == "NO_SESSION_CONTEXT"
