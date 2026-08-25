from decimal import Decimal

from edward.ui.instrument_screen import decimal, field, items


def test_decimal_supports_quotation_payload():
    assert decimal({"units": "315", "nano": 420000000}) == Decimal("315.42")


def test_decimal_invalid_value_returns_zero():
    assert decimal("not-a-price") == Decimal("0")


def test_field_supports_dict_and_object():
    assert field({"ticker": "SBER"}, "ticker") == "SBER"

    class Instrument:
        ticker = "AAPL"

    assert field(Instrument(), "ticker") == "AAPL"


def test_items_extracts_named_collection():
    assert items({"last_prices": [{"price": 1}]}, "last_prices") == [{"price": 1}]


def test_items_accepts_list_response():
    assert items([1, 2]) == [1, 2]
