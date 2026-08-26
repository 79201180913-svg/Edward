from decimal import Decimal
from uuid import UUID

from edward.api.tinvest_adapter_client import TInvestAdapterClient


class Request:
    quantity = Decimal("1000")
    side = "SELL"
    account_id = "acc-1"
    order_type = "LIMIT"
    instrument_uid = "uid-1"
    execution_id = "acc-1:uid-1:REDUCE:1000"
    entry_price = Decimal("10.42")


def test_order_payload_normalizes_execution_id_to_uuid():
    payload = TInvestAdapterClient._order_payload(Request())

    UUID(payload["request_id"])
    assert payload["request_id"] != Request.execution_id
    assert payload["quantity"] == 1000
    assert payload["direction"] == "SELL"
    assert payload["price"] == {"units": "10", "nano": 420000000}


def test_order_request_id_is_deterministic_for_same_execution_id():
    first = TInvestAdapterClient._order_request_id(Request())
    second = TInvestAdapterClient._order_request_id(Request())
    assert first == second
    UUID(first)


def test_existing_uuid_request_id_is_preserved():
    class UuidRequest(Request):
        request_id = "550e8400-e29b-41d4-a716-446655440000"

    assert TInvestAdapterClient._order_request_id(UuidRequest()) == UuidRequest.request_id
