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

    def find_instrument(self, query, trade_available_only=True):
        return {"instruments": []}


def test_catalog_list_returns_authoritative_list():
    client = FakeCatalogClient()
    service = InstrumentCatalogService(client)

    result = service.list("SHARE")

    assert [item.ticker for item in result] == ["SBER", "GAZP"]
    assert client.list_calls == [("SHARE", True)]


def test_catalog_search_falls_back_to_authoritative_list_on_not_found():
    client = FakeCatalogClient()
    service = InstrumentCatalogService(client)

    result = service.search("sber", "SHARE")

    assert len(result) == 1
    assert result[0].ticker == "SBER"
    assert client.list_calls == [("SHARE", True)]
