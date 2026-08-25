from __future__ import annotations

import json
import os
import time
import uuid
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from tests.e2e.test_sandbox_end_to_end import (
    _get_account_id,
    _get_tradable_instrument,
    _items,
    _request,
    _number,
    sandbox_adapter,
)


def _request_stop(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:8765{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Stop-order HTTP {exc.code} {path}: {raw}") from exc


def _position_in_account(account_id: str) -> tuple[str, int, Decimal]:
    positions = _request("POST", "/accounts/sandbox-positions", {"account_id": account_id})
    for item in _items(positions, "securities"):
        balance = int(abs(_number(item.get("balance", 0))))
        uid = str(item.get("instrument_uid") or item.get("uid") or "")
        if uid and balance > 0:
            prices = _request("POST", "/market/last-prices", {"instrument_ids": [uid]})
            prices_items = _items(prices, "last_prices")
            if prices_items:
                price = _number(prices_items[0].get("price", 0))
                if price > 0:
                    return uid, balance, price
    pytest.skip("Sandbox account has no position suitable for protective-order E2E")


def _create_stop(account_id: str, uid: str, side: str, kind: str, quantity: int, stop_price: Decimal, price: Decimal | None = None) -> dict:
    payload = {
        "account_id": account_id,
        "instrument_uid": uid,
        "instrument_id": uid,
        "direction": side,
        "quantity": quantity,
        "stop_price": str(stop_price),
        "price": str(price) if price is not None else None,
        "stop_order_type": kind,
        "expiration_type": "STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL",
        "exchange_order_type": "EXCHANGE_ORDER_TYPE_LIMIT" if kind.endswith("STOP_LIMIT") else "EXCHANGE_ORDER_TYPE_MARKET",
        "take_profit_type": "TAKE_PROFIT_TYPE_REGULAR" if kind.endswith("TAKE_PROFIT") else "TAKE_PROFIT_TYPE_UNSPECIFIED",
        "price_type": "PRICE_TYPE_CURRENCY",
        "order_id": str(uuid.uuid4()),
    }
    return _request_stop("POST", "/stop-orders/create", payload)


def _list_stops(account_id: str) -> list[dict]:
    response = _request_stop("POST", "/stop-orders", {"account_id": account_id})
    return _items(response, "stop_orders")


def _cancel_stop(account_id: str, stop_order_id: str) -> dict:
    return _request_stop("POST", "/stop-orders/cancel", {"account_id": account_id, "stop_order_id": stop_order_id})


@pytest.mark.parametrize(
    "kind, stop_multiplier, side",
    [
        ("STOP_ORDER_TYPE_STOP_LOSS", Decimal("0.50"), "STOP_ORDER_DIRECTION_SELL"),
        ("STOP_ORDER_TYPE_TAKE_PROFIT", Decimal("1.50"), "STOP_ORDER_DIRECTION_SELL"),
    ],
)
def test_sandbox_protective_order_create_get_cancel(kind, stop_multiplier, side, sandbox_adapter):
    if os.getenv("EDWARD_E2E_TRADING", "0") != "1":
        pytest.skip("Protective-order E2E requires EDWARD_E2E_TRADING=1")

    account_id = _get_account_id()
    uid, balance, current = _position_in_account(account_id)
    stop_price = (current * stop_multiplier).quantize(Decimal("0.0001"))
    if stop_price <= 0:
        pytest.skip("Derived protective price is not positive")

    created = _create_stop(account_id, uid, side, kind, 1, stop_price)
    stop_id = str(created.get("stop_order_id") or "")
    assert stop_id, f"Sandbox did not return stop_order_id: {created}"

    try:
        active = _list_stops(account_id)
        matching = [item for item in active if str(item.get("stop_order_id") or "") == stop_id]
        assert matching, f"Created stop order is missing from GetSandboxStopOrders: {active}"
    finally:
        _cancel_stop(account_id, stop_id)

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        active = _list_stops(account_id)
        if not any(str(item.get("stop_order_id") or "") == stop_id for item in active):
            return
        time.sleep(0.5)
    pytest.fail("Cancelled protective order remained in active stop-order list")


def test_sandbox_stop_limit_create_get_cancel(sandbox_adapter):
    if os.getenv("EDWARD_E2E_TRADING", "0") != "1":
        pytest.skip("Protective-order E2E requires EDWARD_E2E_TRADING=1")

    account_id = _get_account_id()
    uid, balance, current = _position_in_account(account_id)
    stop_price = (current * Decimal("0.50")).quantize(Decimal("0.0001"))
    limit_price = (current * Decimal("0.49")).quantize(Decimal("0.0001"))
    if stop_price <= 0 or limit_price <= 0:
        pytest.skip("Derived stop-limit prices are not positive")

    created = _create_stop(
        account_id,
        uid,
        "STOP_ORDER_DIRECTION_SELL",
        "STOP_ORDER_TYPE_STOP_LIMIT",
        1,
        stop_price,
        price=limit_price,
    )
    stop_id = str(created.get("stop_order_id") or "")
    assert stop_id, f"Sandbox did not return stop_order_id: {created}"

    try:
        active = _list_stops(account_id)
        matching = [item for item in active if str(item.get("stop_order_id") or "") == stop_id]
        assert matching, f"Created stop-limit is missing from GetSandboxStopOrders: {active}"
    finally:
        _cancel_stop(account_id, stop_id)
