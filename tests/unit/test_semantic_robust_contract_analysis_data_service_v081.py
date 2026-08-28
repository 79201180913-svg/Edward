from edward.services.semantic_robust_contract_analysis_data_service_v081 import SemanticRobustContractAnalysisDataServiceV081


class EmptyCollectionsClient:
    def get_asset_fundamentals(self, instrument_id):
        return {"fundamentals": []}

    def get_order_book(self, instrument_id, depth):
        return {"bids": [], "asks": []}

    def get_last_trades(self, instrument_id, from_dt, to_dt):
        return {"trades": []}

    def get_signals(self, **kwargs):
        return {"signals": []}

    def get_dividends(self, instrument_id, from_dt, to_dt):
        return {"dividends": []}

    def get_insider_deals(self, instrument_id, limit):
        return {"insider_deals": []}

    def get_risk_rates(self, instrument_ids):
        return {"instrument_risk_rates": []}

    def get_asset_reports(self, instrument_id, from_dt, to_dt):
        return {"events": []}

    def get_news(self, limit):
        return {"items": []}

    def get_trading_schedules(self, **kwargs):
        return {"exchanges": []}


def test_empty_valid_contract_collections_are_not_reported_as_mapping_failures():
    result = SemanticRobustContractAnalysisDataServiceV081(EmptyCollectionsClient()).collect("UID")

    assert "fundamentals_mapping" not in result.failed_sources
    assert "insiders_mapping" not in result.failed_sources
    assert "reports_mapping" not in result.failed_sources
    assert "risk_rates_mapping" not in result.failed_sources
    assert result.fundamentals is None
    assert result.risk_data is None
    assert result.reports == ()
    assert result.insider_transactions == ()


class ErrorRiskClient(EmptyCollectionsClient):
    def get_risk_rates(self, instrument_ids):
        return {
            "instrument_risk_rates": [
                {
                    "instrument_uid": instrument_ids[0],
                    "error": "Risk rates are unavailable for this instrument",
                }
            ]
        }


def test_contract_risk_error_is_unavailable_not_mapping_failure():
    result = SemanticRobustContractAnalysisDataServiceV081(ErrorRiskClient()).collect("UID")

    assert result.risk_data is None
    assert "risk_rates_mapping" not in result.failed_sources


class NestedRiskRateClient(EmptyCollectionsClient):
    def get_risk_rates(self, instrument_ids):
        return {
            "instrument_risk_rates": [
                {
                    "instrument_uid": instrument_ids[0],
                    "long_risk_rate": {"value": 0.30},
                    "short_risk_rate": {"value": 0.55},
                }
            ]
        }


def test_nested_contract_risk_rates_are_mapped_during_semantic_retry():
    result = SemanticRobustContractAnalysisDataServiceV081(NestedRiskRateClient()).collect("UID")

    assert "risk_rates_mapping" not in result.failed_sources
    assert result.risk_data is not None
    assert result.risk_data["dlong"] == 0.30
    assert result.risk_data["dshort"] == 0.55
    assert result.risk_data["dlong_client"] == 0.30
    assert result.risk_data["dshort_client"] == 0.55


class EmptyRateArraysClient(EmptyCollectionsClient):
    def get_risk_rates(self, instrument_ids):
        return {
            "instrument_risk_rates": [
                {
                    "instrument_uid": instrument_ids[0],
                    "long_risk_rates": [],
                    "short_risk_rates": [],
                }
            ]
        }


def test_empty_risk_rate_arrays_are_unavailable_not_mapping_failure():
    result = SemanticRobustContractAnalysisDataServiceV081(EmptyRateArraysClient()).collect("UID")

    assert result.risk_data is None
    assert "risk_rates_mapping" not in result.failed_sources
    assert "risk_rates" in result.unavailable_sources
