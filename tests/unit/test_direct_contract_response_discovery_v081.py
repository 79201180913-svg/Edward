from edward.services.robust_contract_analysis_data_service_v081 import RobustContractAnalysisDataServiceV081


class DirectClient:
    def get_asset_fundamentals(self, instrument_id):
        return {
            "roe": 18.0,
            "roic": 15.0,
            "net_margin_mrq": 10.0,
            "revenue_ttm": {"units": "100", "nano": 0},
            "free_cash_flow_ttm": {"units": "12", "nano": 0},
            "pe_ratio_ttm": 10.0,
        }

    def get_order_book(self, instrument_id, depth):
        return {"bids": [{"price": 99.5, "quantity": 100}], "asks": [{"price": 100.5, "quantity": 80}]}

    def get_last_trades(self, instrument_id, from_dt, to_dt):
        return {"trades": [{"direction": "BUY", "quantity": 100}]}

    def get_signals(self, **kwargs):
        return {"signals": [{"signal_id": "S1", "direction": "BUY", "initial_price": 100, "close_price": 105}]}

    def get_dividends(self, instrument_id, from_dt, to_dt):
        return {"dividends": [{"yield_value": 4, "regularity": 1}]}

    def get_insider_deals(self, instrument_id, limit):
        return {"insider_deals": [{"direction": "BUY", "price": 100, "quantity": 10}]}

    def get_risk_rates(self, instrument_ids):
        return {"long_risk_rate": 12, "short_risk_rate": 20}

    def get_asset_reports(self, instrument_id, from_dt, to_dt):
        return {"report_date": "2099-09-01T00:00:00Z", "period_year": 2099}

    def get_news(self, limit):
        return {"id": 1, "source": "test", "title": "News"}

    def get_trading_schedules(self, **kwargs):
        return {"exchanges": []}


def test_direct_contract_objects_are_mapped_without_mapping_failures():
    result = RobustContractAnalysisDataServiceV081(DirectClient()).collect("UID")

    assert result.fundamentals is not None
    assert result.fundamentals["roe"] == 18.0
    assert result.risk_data is not None
    assert result.risk_data["dlong_client"] == 12.0
    assert len(result.reports) == 1
    assert len(result.insider_transactions) == 1
    assert len(result.news) == 1
    assert "fundamentals_mapping" not in result.failed_sources
    assert "risk_rates_mapping" not in result.failed_sources
    assert "reports_mapping" not in result.failed_sources
    assert "insiders_mapping" not in result.failed_sources
    assert "news_mapping" not in result.failed_sources
