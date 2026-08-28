from datetime import datetime, timedelta, timezone

from edward.services.contract_analysis_data_service_v081 import ContractAnalysisDataServiceV081


class FakeClient:
    def __init__(self):
        self.schedule_from = None
        self.schedule_to = None

    def get_instrument(self, instrument_id):
        return {
            "instrument": {
                "instrument_uid": instrument_id,
                "dlong_client": 0.30,
                "dshort_client": 0.55,
                "short_enabled_flag": True,
            }
        }

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
        self.schedule_from = kwargs.get("from_dt")
        self.schedule_to = kwargs.get("to_dt")
        return {"exchanges": []}


def test_collector_returns_mapped_contract_sources_and_tracks_failures():
    client = FakeClient()
    result = ContractAnalysisDataServiceV081(client).collect("UID")

    assert result.fundamentals["free_cash_flow"] == 10.0
    assert result.order_book["bids"][0]["price"] == 99.0
    assert result.trades[0]["quantity"] == 100.0
    assert result.signals[0]["signal_id"] == "S1"
    assert result.dividends["dividend_yield"] == 4.0
    assert result.insider_transactions[0]["quantity"] == 10.0
    assert result.risk_data["dlong_client"] == 10.0
    assert result.instrument_risk_metadata["dlong_client"] == 0.30
    assert result.instrument_risk_metadata["dshort_client"] == 0.55
    assert result.instrument_risk_metadata["short_enabled"] is True
    assert result.news[0]["id"] == 1
    assert result.session_name is None
    assert result.session_available is False
    assert set(result.failed_sources) == set()
    assert isinstance(client.schedule_from, datetime)
    assert isinstance(client.schedule_to, datetime)
    assert client.schedule_from.tzinfo is not None
    assert client.schedule_to.tzinfo is not None
    assert client.schedule_from >= datetime.now(timezone.utc) - timedelta(seconds=5)
    assert client.schedule_to > client.schedule_from


def test_collector_keeps_instrument_metadata_separate_when_risk_rates_are_empty():
    class NoRiskRatesClient(FakeClient):
        def get_risk_rates(self, instrument_ids):
            return {"instrument_risk_rates": [{"long_risk_rates": [], "short_risk_rates": []}]}

    result = ContractAnalysisDataServiceV081(NoRiskRatesClient()).collect("UID")

    assert result.risk_data is None
    assert result.instrument_risk_metadata is not None
    assert result.instrument_risk_metadata["dlong_client"] == 0.30
    assert result.instrument_risk_metadata["dshort_client"] == 0.55
    assert result.instrument_risk_metadata["short_enabled"] is True
    assert "risk_rates_mapping" in result.unavailable_sources
    assert "risk_rates_mapping" not in result.failed_sources


def test_collector_accepts_camel_case_contract_wrappers():
    class CamelClient(FakeClient):
        def get_asset_fundamentals(self, instrument_id):
            return {"fundamentals": [{"roe": 15, "roic": 13, "freeCashFlowTtm": 10, "peRatioTtm": 10}]}

        def get_asset_reports(self, instrument_id, from_dt, to_dt):
            return {"events": [{"instrumentId": instrument_id, "reportDate": "2026-09-01T00:00:00Z"}]}

    result = ContractAnalysisDataServiceV081(CamelClient()).collect("UID")

    assert result.fundamentals is not None
    assert result.fundamentals["free_cash_flow"] == 10.0
    assert result.reports[0]["instrument_id"] == "UID"
    assert result.reports[0]["report_date"] == "2026-09-01T00:00:00Z"


def test_collector_accepts_nested_response_wrapper_for_fundamentals():
    class NestedClient(FakeClient):
        def get_asset_fundamentals(self, instrument_id):
            return {
                "response": {
                    "data": {
                        "statistics": [{"roe": 24, "roic": 19, "free_cash_flow_ttm": 12}]
                    }
                }
            }

    result = ContractAnalysisDataServiceV081(NestedClient()).collect("UID")

    assert result.fundamentals is not None
    assert result.fundamentals["roe"] == 24.0
    assert result.fundamentals["roic"] == 19.0
    assert result.fundamentals["free_cash_flow"] == 12.0
    assert "fundamentals" not in result.unavailable_sources


def test_collector_marks_successful_empty_fundamentals_as_unavailable_not_failed():
    class EmptyFundamentalsClient(FakeClient):
        def get_asset_fundamentals(self, instrument_id):
            return {"fundamentals": []}

    result = ContractAnalysisDataServiceV081(EmptyFundamentalsClient()).collect("UID")

    assert result.fundamentals is None
    assert "fundamentals" in result.unavailable_sources
    assert "fundamentals_mapping" not in result.failed_sources


def test_collector_does_not_mark_empty_schedule_response_as_mapping_failure():
    result = ContractAnalysisDataServiceV081(FakeClient()).collect("UID")

    assert "trading_schedules_mapping" not in result.failed_sources
    assert result.session_available is False


class FailingClient(FakeClient):
    def get_order_book(self, instrument_id, depth):
        raise RuntimeError("order book unavailable")


def test_collector_degrades_gracefully_when_optional_endpoint_fails():
    result = ContractAnalysisDataServiceV081(FailingClient()).collect("UID")

    assert result.order_book is None
    assert "order_book" in result.failed_sources
    assert result.fundamentals is not None
