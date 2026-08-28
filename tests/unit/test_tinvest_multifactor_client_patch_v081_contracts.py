from edward.api.tinvest_multifactor_client_patch_v081 import (
    get_asset_fundamentals,
    get_risk_rates,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    def _request(self, method, path, payload):
        self.calls.append((method, path, payload))
        return {"ok": True}


def test_asset_fundamentals_uses_contract_assets_field():
    client = FakeClient()

    result = get_asset_fundamentals(client, "UID")

    assert result == {"ok": True}
    assert client.calls == [
        ("POST", "/analysis/fundamentals", {"assets": ["UID"]}),
    ]


def test_risk_rates_uses_contract_instrument_id_field():
    client = FakeClient()

    result = get_risk_rates(client, ["UID-1", "UID-2"])

    assert result == {"ok": True}
    assert client.calls == [
        ("POST", "/analysis/risk-rates", {"instrument_id": ["UID-1", "UID-2"]}),
    ]
