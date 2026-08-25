from decimal import Decimal

from edward.ui.instrument_screen_ux_v03 import _decimal, _fmt, _status_text


def test_decimal_supports_quotation_payload():
    assert _decimal({"units": "876", "nano": 0}) == Decimal("876")


def test_fmt_hides_internal_quotation_shape():
    assert _fmt({"units": "1", "nano": 0}, 8) == "1"


def test_status_is_human_readable():
    assert _status_text("SECURITY_TRADING_STATUS_NORMAL_TRADING") == "Торги идут"


def test_unknown_status_is_preserved():
    assert _status_text("SOMETHING_NEW") == "SOMETHING_NEW"
