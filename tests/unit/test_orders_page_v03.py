from decimal import Decimal

from edward.ui.orders_page_v03 import human_direction, human_order_type, human_status, order_row, remaining_quantity


def test_status_is_user_friendly():
    assert human_status("EXECUTION_REPORT_STATUS_NEW") == "Новая"
    assert human_status("EXECUTION_REPORT_STATUS_FILL") == "Исполнена"
    assert human_status("EXECUTION_REPORT_STATUS_PARTIALLYFILL") == "Частично исполнена"
    assert human_status("EXECUTION_REPORT_STATUS_CANCELLED") == "Отменена"


def test_direction_and_order_type_are_user_friendly():
    assert human_direction("BUY") == "Покупка"
    assert human_direction("SELL") == "Продажа"
    assert human_order_type("MARKET") == "Рыночная"
    assert human_order_type("LIMIT") == "Лимитная"
    assert human_order_type("BESTPRICE") == "Лучшая цена"


def test_remaining_quantity_is_never_negative():
    assert remaining_quantity("10", "4") == Decimal("6")
    assert remaining_quantity("10", "12") == Decimal("0")


def test_order_row_normalizes_lifecycle_fields():
    row = order_row(
        {
            "order_id": "order-1",
            "ticker": "VLHZ",
            "instrument_uid": "uid-1",
            "direction": "BUY",
            "order_type": "LIMIT",
            "lots_requested": 10,
            "lots_executed": 4,
            "execution_report_status": "EXECUTION_REPORT_STATUS_PARTIALLYFILL",
            "initial_security_price": {"units": "134", "nano": 0},
        }
    )

    assert row["order_id"] == "order-1"
    assert row["direction"] == "Покупка"
    assert row["order_type"] == "Лимитная"
    assert row["requested"] == Decimal("10")
    assert row["executed"] == Decimal("4")
    assert row["remaining"] == Decimal("6")
    assert row["status"] == "Частично исполнена"
    assert row["price"] == Decimal("134")
