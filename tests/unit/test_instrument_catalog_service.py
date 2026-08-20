from edward.services.instrument_catalog_service import InstrumentCatalogService


class FakeClient:
    def __init__(self):
        self.catalog = {
            "instruments": [
                {"ticker": "SBER", "name": "Сбербанк", "uid": "uid-sber", "figi": "figi-sber"},
                {"ticker": "GAZP", "name": "Газпром", "uid": "uid-gazp", "figi": "figi-gazp"},
            ]
        }

    def list_instruments(self, instrument_kind="SHARE", trade_available_only=True):
        return self.catalog

    def find_instrument(self, query, trade_available_only=True):
        raise RuntimeError("not_found")


def test_instrument_catalog_returns_list():
    service = InstrumentCatalogService(FakeClient())

    instruments = service.list()

    assert len(instruments) == 2
    assert instruments[0]["ticker"] == "SBER"


def test_instrument_catalog_search_falls_back_to_local_list():
    service = InstrumentCatalogService(FakeClient())

    instruments = service.search("Sber")

    assert len(instruments) == 1
    assert instruments[0]["ticker"] == "SBER"
