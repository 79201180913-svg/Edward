from edward.ui.decision_context_ui_v04 import _field


def test_field_reads_dict_value():
    assert _field({"ticker": "UNAC"}, "ticker") == "UNAC"


def test_field_reads_object_attribute():
    class Instrument:
        ticker = "UNAC"

    assert _field(Instrument(), "ticker") == "UNAC"


def test_field_returns_default_for_missing_value():
    assert _field({}, "ticker", "—") == "—"
