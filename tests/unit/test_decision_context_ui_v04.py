from edward.ui.decision_context_ui_v04 import _quotation_to_text


def test_quotation_to_text_string():
    assert _quotation_to_text("321.45") == "321.45"


def test_quotation_to_text_units_and_nano():
    assert _quotation_to_text({"units": 321, "nano": 450000000}) == "321.4500"


def test_quotation_to_text_empty():
    assert _quotation_to_text(None) == "—"
