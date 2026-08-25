from edward.ui.instrument_screen import format_price_increment, instrument_detail_from_catalog


def test_instrument_detail_uses_catalog_without_api_lookup():
    detail = {
        "ticker": "UNAC",
        "name": "United Aircraft",
        "currency": "RUB",
        "last_price": "70.12",
        "min_price_increment": "0.01",
        "buy_available": True,
        "sell_available": True,
        "api_trade_available": True,
        "uid": "uid-1",
        "instrument_uid": "uid-1",
        "instrument_kind": "SHARE",
    }

    result = instrument_detail_from_catalog(detail)

    assert result["ticker"] == "UNAC"
    assert result["name"] == "United Aircraft"
    assert result["instrument_uid"] == "uid-1"
    assert result["buy_available"] is True
    assert result["sell_available"] is True


def test_zero_price_increment_is_not_displayed_as_real_value():
    assert format_price_increment(0) == "—"
    assert format_price_increment(None) == "—"
    assert format_price_increment("") == "—"


def test_positive_price_increment_is_formatted():
    assert format_price_increment({"units": "0", "nano": 1000000}) == "0.001"
