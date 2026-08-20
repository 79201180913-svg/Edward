from edward.services.instrument_catalog_service import InstrumentCatalogService


class FakeClient:
    def __init__(self):
        self.find_called = False
        self.catalog = {
            "instruments": [
                {"ticker": "SBER", "name": "Сбербанк", "uid": "uid-sber", "figi": "figi-sber"},
                {"ticker": "GAZP", "name": "Газпром", "uid": "uid-gazp", "figi": "figi-gazp"},
            ]
        }

    def list_instruments(self, instrument_kind="SHARE", trade_available_only=True):
        return self.catalog

    def find_instrument(self, query, trade_available_only=True):
        self.find_called = True
        raise RuntimeError("not_found")


def test_instrument_catalog_returns_list():
    service = InstrumentCatalogService(FakeClient())

    instruments = service.list()

    assert len(instruments) == 2
    assert instruments[0]["ticker"] == "SBER"


def test_instrument_catalog_search_filters_locally_without_find_endpoint():
    client = FakeClient()
    service = InstrumentCatalogService(client)

    instruments = service.search("Sber")

    assert len(instruments) == 1
    assert instruments[0]["ticker"] == "SBER"
    assert client.find_called is False


def test_instrument_catalog_search_matches_uid_figi_and_isin():
    client = FakeClient()
    client.catalog["instruments"][0]["isin"] = "RU0009029540"
    service = InstrumentCatalogService(client)

    assert service.search("uid-sber")[0]["ticker"] == "SBER"
    assert service.search("figi-sber")[0]["ticker"] == "SBER"
    assert service.search("RU0009029540")[0]["ticker"] == "SBER"
