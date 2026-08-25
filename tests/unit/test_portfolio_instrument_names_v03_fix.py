from edward.ui.portfolio_instrument_names_v03_fix import _instrument_name


def test_instrument_name_from_direct_response():
    assert _instrument_name({"name": "Владимирский химический завод"}) == "Владимирский химический завод"


def test_instrument_name_from_nested_instrument():
    assert _instrument_name({"instrument": {"name": "Кубаньэнерго"}}) == "Кубаньэнерго"


def test_instrument_name_returns_empty_when_missing():
    assert _instrument_name({"ticker": "VLHZ"}) == ""
