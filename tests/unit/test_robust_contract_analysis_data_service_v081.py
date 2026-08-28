from edward.services.robust_contract_analysis_data_service_v081 import RobustContractAnalysisDataServiceV081


class NestedClient:
    def get_asset_fundamentals(self, instrument_id):
        return {
            "data": {
                "response": {
                    "statistics": [{
                        "roe": 18.0,
                        "roic": 15.0,
                        "net_margin_mrq": 10.0,
                        "one_year_annual_revenue_growth_rate": 12.0,
                        "eps_change_five_years": 30.0,
                        "ebitda_change_five_years": 25.0,
                        "net_debt_to_ebitda": 1.0,
                        "current_ratio_mrq": 1.8,
                        "revenue_ttm": {"units": "100", "nano": 0},
                        "free_cash_flow_ttm": {"units": "12", "nano": 0},
                        "pe_ratio_ttm": 10.0,
                    }]
                }
            }
        }

    def get_order_book(self, instrument_id, depth):
        return {"data": {"bids": [{"price": 99.5, "quantity": 100}], "asks": [{"price": 100.5, "quantity": 80}]}}

    def get_last_trades(self, instrument_id, from_dt, to_dt):
        return {"data": {"trades": [{"direction": "TRADE_DIRECTION_BUY", "quantity": 100}]}}

    def get_signals(self, **kwargs):
        return {"data": {"signals": [{"signal_id": "S1", "direction": "SIGNAL_DIRECTION_BUY", "initial_price": 100, "close_price": 105}]}}

    def get_dividends(self, instrument_id, from_dt, to_dt):
        return {"data": {"dividends": [{"yield_value": 4, "regularity": 1}]}}

    def get_insider_deals(self, instrument_id, limit):
        return {"data": {"insider_deals": [{"direction": "TRADE_DIRECTION_BUY", "price": 100, "quantity": 10}]}}

    def get_risk_rates(self, instrument_ids):
        return {"data": {"risk_rates": [{"long_risk_rate": 12, "short_risk_rate": 20}]}}

    def get_asset_reports(self, instrument_id, from_dt, to_dt):
        return {"data": {"events": [{"instrument_id": instrument_id, "report_date": "2099-09-01T00:00:00Z"}]}}

    def get_news(self, limit):
        return {"data": {"items": [{"id": 1, "instrument_id": [{"instrument": {"instrument_uid": "UID"}}}]}}

    def get_trading_schedules(self, **kwargs):
        return {"data": {"exchanges": []}}


def test_nested_contract_envelopes_are_unwrapped_without_mapping_failures():
    result = RobustContractAnalysisDataServiceV081(NestedClient()).collect("UID")

    assert result.fundamentals is not None
    assert result.fundamentals["roe"] == 18.0
    assert result.order_book is not None
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


def test_unavailable_risk_does_not_become_neutral_score():
    class EmptyRiskClient(NestedClient):
        def get_risk_rates(self, instrument_ids):
            return {"data": {"risk_rates": []}}

    result = RobustContractAnalysisDataServiceV081(EmptyRiskClient()).collect("UID")

    assert result.risk_data is None
