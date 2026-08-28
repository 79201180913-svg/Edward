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
