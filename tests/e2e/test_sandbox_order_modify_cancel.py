from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest

from tests.e2e.test_sandbox_end_to_end import (
    _get_account_id,
    _get_tradable_instrument,
    _request,
    _wait_terminal,
    _cancel_if_active,
    sandbox_adapter,
)


ORDER_TIMEOUT_MESSAGE = "Sandbox order did not remain active long enough for replacement"


def _create_resting_limit_order(account_id: str, instrument_uid: str, price: Decimal) -> dict:
    request_id = str(uuid.uuid4())
    return _request(
        "POST",
        "/orders/create",
        {
            "account_id": account_id,
            "instrument_uid": instrument_uid,
            "instrument_id": instrument_uid,
            "direction": "BUY",
            "order_type": "LIMIT",
            "quantity": 1,
            "price": str(price),
            "order_id": request_id,
            "request_id": request_id,
            "price_type": "PRICE_TYPE_CURRENCY",
        },
    )


def _replace_limit_order(
    account_id: str,
    instrument_uid: str,
    order_id: str,
    quantity: int,
    price: Decimal,
) -> dict:
    request_id = str(uuid.uuid4())
    return _request(
        "POST",
        "/orders/replace",
        {
            "account_id": account_id,
            "instrument_uid": instrument_uid,
            "instrument_id": instrument_uid,
            "direction": "BUY",
            "order_type": "LIMIT",
            "quantity": quantity,
            "price": str(price),
            "order_id": order_id,
            "request_id": request_id,
            "price_type": "PRICE_TYPE_CURRENCY",
        },
    )


def _status(order: dict) -> str:
    return str(
        order.get("execution_report_status")
        or order.get("status")
        or order.get("state")
        or ""
    ).upper()


def test_sandbox_order_modify_then_cancel_end_to_end(sandbox_adapter):
    """Create a resting Sandbox LIMIT order, replace it, then cancel it.

    Enabled only with EDWARD_E2E_TRADING=1. The order is deliberately placed
    well below the market so the scenario exercises replacement rather than
    immediate execution. Any unexpected terminal state is surfaced explicitly
    instead of leaving an active order behind.
    """
    if os.getenv("EDWARD_E2E_TRADING", "0") != "1":
        pytest.skip("Trading E2E requires EDWARD_E2E_TRADING=1")

    account_id = _get_account_id()
    instrument_uid, market_price = _get_tradable_instrument()
    assert market_price > 0

    initial_price = (market_price * Decimal("0.50")).quantize(Decimal("0.0001"))
    replacement_price = (market_price * Decimal("0.49")).quantize(Decimal("0.0001"))
    assert initial_price > 0
    assert replacement_price > 0
    assert replacement_price < initial_price < market_price

    created = _create_resting_limit_order(account_id, instrument_uid, initial_price)
    order_id = str(created.get("order_id") or created.get("id") or "")
    assert order_id, f"Sandbox did not return order_id: {created}"

    state = _request(
        "POST",
        "/orders/state",
        {"account_id": account_id, "order_id": order_id},
    )
    initial_status = _status(state)
    if "FILL" in initial_status or "CANCEL" in initial_status or "REJECT" in initial_status:
        pytest.fail(f"{ORDER_TIMEOUT_MESSAGE}: {state}")

    try:
        replaced = _replace_limit_order(
            account_id,
            instrument_uid,
            order_id,
            quantity=2,
            price=replacement_price,
        )
        replaced_id = str(replaced.get("order_id") or replaced.get("id") or order_id)
        assert replaced_id

        replaced_state = _request(
            "POST",
            "/orders/state",
            {"account_id": account_id, "order_id": replaced_id},
        )
        replaced_status = _status(replaced_state)
        assert "REJECT" not in replaced_status
        assert "FAIL" not in replaced_status

        requested = int(str(replaced_state.get("lots_requested", 0) or 0))
        if requested:
            assert requested == 2

        assert Decimal(str(replaced_state.get("initial_security_price", replaced_state.get("price", replacement_price)))) == replacement_price
    finally:
        try:
            cancelled = _cancel_if_active(account_id, replaced_id if "replaced_id" in locals() else order_id)
            cancelled_status = _status(cancelled)
            if cancelled_status:
                assert any(
                    marker in cancelled_status
                    for marker in ("CANCEL", "INACTIVE", "REJECT")
                ), f"Unexpected cancellation response: {cancelled}"
        except Exception:
            # Fetch final state so the failure contains useful broker-side evidence.
            final_state = _request(
                "POST",
                "/orders/state",
                {"account_id": account_id, "order_id": replaced_id if "replaced_id" in locals() else order_id},
            )
            final_status = _status(final_state)
            assert any(
                marker in final_status
                for marker in ("CANCEL", "INACTIVE", "REJECT")
            ), f"Order was not cancelled: {final_state}"
