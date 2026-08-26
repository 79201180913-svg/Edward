from decimal import Decimal

from edward.ui.autonomous_portfolio_ui_v07 import _decimal, _field, _items, _money


def test_portfolio_ui_helpers_support_t_invest_money_values():
    assert _decimal({"units": 125, "nano": 500000000}) == Decimal("125.5")
    assert _money(Decimal("125.5"), "RUB") == "125.50 RUB"


def test_portfolio_ui_helpers_support_dict_and_object_responses():
    assert _field({"ticker": "TEST"}, "ticker") == "TEST"
    assert _items({"securities": [{"ticker": "TEST"}]}, "securities") == [{"ticker": "TEST"}]
