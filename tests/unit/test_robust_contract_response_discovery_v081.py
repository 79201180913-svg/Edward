from edward.services.robust_contract_analysis_data_service_v081 import RobustContractAnalysisDataServiceV081


def test_fundamentals_unwraps_nested_statistics_object():
    payload = {"data": {"response": {"fundamentals": {"statistics": {"roe": 18.0, "roic": 15.0}}}}}

    value = RobustContractAnalysisDataServiceV081._first(payload, "fundamentals", "statistics")

    assert value == {"roe": 18.0, "roic": 15.0}


def test_reports_unwraps_nested_events_items_list():
    payload = {"response": {"events": {"items": [{"report_date": "2099-09-01T00:00:00Z"}]}}}

    value = RobustContractAnalysisDataServiceV081._many(payload, "events")

    assert value == [{"report_date": "2099-09-01T00:00:00Z"}]


def test_risk_rates_accepts_direct_result_object():
    payload = {"risk_rates": {"instrument_uid": "UID", "long_risk_rate": {"value": {"units": 12, "nano": 0}}}}

    value = RobustContractAnalysisDataServiceV081._many(payload, "risk_rates")

    assert len(value) == 1
    assert value[0]["instrument_uid"] == "UID"
