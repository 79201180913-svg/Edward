from edward.services.contract_analysis_data_service_v081 import ContractAnalysisDataServiceV081


class FakeClient:
    def get_asset_fundamentals(self, instrument_id):
        return {"fundamentals": [{"roe": 15, "roic": 13, "revenue_ttm": 100, "free_cash_flow_ttm": 10, "pe_ratio_ttm": 10}]}

    def get_order_book(self, instrument_id, depth):
        return {"bids": [{"price": 99, "quantity": 1000}], "asks": [{"price": 101, "quantity": 500}]}

    def get_last_trades(self, instrument_id, from_dt, to_dt):
        return {"trades": [{"direction": "TRADE_DIRECTION_BUY", "quantity": 100}]}

    def get_signals(self, **kwargs):
        return {"signals": [{"signal_id": "S1", "direction": "SIGNAL_DIRECTION_BUY", "initial_price": 100, "close_price": 105}]}

    def get_dividends(self, instrument_id, from_dt, to_dt):
        return {"dividends": [{"yield_value": 4, "regularity": "Annual"}]}

    def get_insider_deals(self, instrument_id, limit):
        return {"insider_deals": [{"direction": "TRADE_DIRECTION_BUY", "price": 100, "quantity": 10}]}

    def get_risk_rates(self, instrument_ids):
        return {"instrument_risk_rates": [{"long_risk_rate": {"value": 10}, "short_risk_rate": {"value": 15}}]}

    def get_asset_reports(self, instrument_id, from_dt, to_dt):
        return {"events": [{"instrument_id": instrument_id, "report_date": "2026-09-01T00:00:00Z"}]}

    def get_news(self, limit):
        return {"items": [{"id": 1, "title": "Test", "instrument_id": [{"instrument": {"instrument_uid": "UID"}}]}]}

    def get_trading_schedules(self, **kwargs):
        return {"exchanges": []}


def test_collector_returns_mapped_contract_sources_and_tracks_failures():
    result = ContractAnalysisDataServiceV081(FakeClient()).collect("UID")

    assert result.fundamentals["free_cash_flow"] == 10.0
    assert result.order_book["bids"][0]["price"] == 99.0
    assert result.trades[0]["quantity"] == 100.0
    assert result.signals[0]["signal_id"] == "S1"
    assert result.dividends["dividend_yield"] == 4.0
    assert result.insider_transactions[0]["quantity"] == 10.0
    assert result.risk_data["dlong_client"] == 10.0
    assert result.news[0]["id"] == 1
    assert set(result.failed_sources) == set()


class FailingClient(FakeClient):
    def get_order_book(self, instrument_id, depth):
        raise RuntimeError("order book unavailable")


def test_collector_degrades_gracefully_when_optional_endpoint_fails():
    result = ContractAnalysisDataServiceV081(FailingClient()).collect("UID")

    assert result.order_book is None
    assert "order_book" in result.failed_sources
    assert result.fundamentals is not None
