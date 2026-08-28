import logging

from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisServiceV082


def test_metric_audit_log_contains_raw_mapped_score_and_direction(caplog):
    snapshot = {
        "roe": 23.44,
        "roic": None,
        "roa": 2.81,
        "net_margin": None,
        "revenue_growth": 25.2,
        "revenue_growth_3y": 33.0,
        "revenue_growth_5y": None,
        "revenue_change_5y": 212.2,
        "eps_growth": 126.9,
        "ebitda_growth": None,
        "__instrument_context": {"sector": "banking"},
    }

    with caplog.at_level(logging.INFO):
        result = FundamentalAnalysisServiceV082.analyze(snapshot, profile="medium_term")

    metric_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == "edward.services.fundamental_analysis_service_v082"
        and "[V082 FUNDAMENTAL METRIC]" in record.getMessage()
    ]

    assert any(
        "metric=roe" in message
        and "raw=23.44" in message
        and "mapped=23.440000" in message
        and "score=" in message
        and "direction=POSITIVE" in message
        for message in metric_logs
    )
    assert any(
        "metric=roic" in message and "status=NOT_APPLICABLE" in message
        for message in metric_logs
    )
    assert any(
        "metric=net_margin" in message
        and "status=UNAVAILABLE" in message
        and "reason=METRIC_UNAVAILABLE" in message
        for message in metric_logs
    )
    assert result.overall_score > 0


def test_metric_audit_log_preserves_zero_as_unavailable_after_mapping():
    snapshot = {"pe": 0.0}

    with caplog.at_level(logging.INFO):
        FundamentalAnalysisServiceV082.analyze(snapshot)

    assert any(
        "metric=pe" in record.getMessage()
        and "status=UNAVAILABLE" in record.getMessage()
        and "raw=0.0" in record.getMessage()
        for record in caplog.records
    )
