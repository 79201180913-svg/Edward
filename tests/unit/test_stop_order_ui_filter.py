from edward.ui.stop_order_ui_v03_fixed import _orders_for_instrument


def test_active_stop_orders_are_filtered_by_instrument_uid():
    orders = [
        {"instrument_uid": "AAA", "stop_order_id": "a1"},
        {"instrument_uid": "BBB", "stop_order_id": "b1"},
        {"instrument_uid": "AAA", "stop_order_id": "a2"},
    ]

    result = _orders_for_instrument(orders, "AAA")

    assert [item["stop_order_id"] for item in result] == ["a1", "a2"]


def test_active_stop_orders_accept_instrument_id_alias():
    orders = [
        {"instrument_id": "AAA", "stop_order_id": "a1"},
        {"instrument_uid": "BBB", "stop_order_id": "b1"},
    ]

    result = _orders_for_instrument(orders, "AAA")

    assert [item["stop_order_id"] for item in result] == ["a1"]
