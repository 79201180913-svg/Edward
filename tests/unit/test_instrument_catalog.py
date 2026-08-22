from types import SimpleNamespace

from edward.services.instrument_catalog_service import InstrumentCatalogService


class FakeCatalogClient:
    def __init__(self):
        self.list_calls = []

    def list_instruments(self, instrument_kind="SHARE", trade_available_only=True):
        self.list_calls.append((instrument_kind, trade_available_only))
        return {
            "instruments": [
                SimpleNamespace(uid="1", ticker="SBER", name="Сбербанк", figi="BBG004730N88"),
                SimpleNamespace(uid="2", ticker="GAZP", name="Газпром", figi="BBG004730RP0"),
            ]
        }

    def get_last_prices(self, instrument_ids):
        return {
            "last_prices": [
                SimpleNamespace(uid="1", price=SimpleNamespace(units=100, nano=0)),
                SimpleNamespace(uid="2", price=SimpleNamespace(units=200, nano=0)),
            ]
        }

    def get_trading_statuses(self, instrument_ids):
        return {
            "trading_statuses": [
                SimpleNamespace(uid="1", api_trade_available_flag=True, limit_order_available_flag=True, market_order_available_flag=True, bestprice_order_available_flag=True, trading_status="SECURITY_TRADING_STATUS_NORMAL_TRADING"),
                SimpleNamespace(uid="2", api_trade_available_flag=True, limit_order_available_flag=True, market_order_available_flag=True, bestprice_order_available_flag=True, trading_status="SECURITY_TRADING_STATUS_NORMAL_TRADING"),
            ]
        }


def test_catalog_list_returns_authoritative_list():
    client = FakeCatalogClient()
    service = InstrumentCatalogService(client)

    result = service.list("SHARE")

    assert [item.ticker for item in result] == ["SBER", "GAZP"]
    assert [item.last_price for item in result] == ["100", "200"]
    assert all(item.trading_available for item in result)
    assert client.list_calls == [("SHARE", True)]


def test_catalog_search_falls_back_to_authoritative_list_on_not_found():
    client = FakeCatalogClient()
    service = InstrumentCatalogService(client)

    result = service.search("sber", "SHARE")

    assert len(result) == 1
    assert result[0].ticker == "SBER"
    assert client.list_calls == [("SHARE", True)]
