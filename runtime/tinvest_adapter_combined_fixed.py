from __future__ import annotations

"""Canonical Sandbox adapter combining the fixed orders, operations and stop-order contracts."""

import uuid
import tinvest_adapter_fixed as fixed
import tinvest_candles_patch

_adapter = fixed._adapter


def _operations(self, account_id, limit=1000):
    limit = max(1, min(int(limit), 1000))
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(self._service("operations").get_operations_by_cursor(account_id=str(account_id), limit=limit, without_commissions=False, without_trades=False))
    return self._rest_request("SandboxService/GetSandboxOperationsByCursor", {"accountId": str(account_id), "limit": limit, "withoutCommissions": False, "withoutTrades": False})


def _orders(self, account_id):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(self._service("orders").get_orders(account_id=str(account_id)))
    return self._rest_request("SandboxService/GetSandboxOrders", {"accountId": str(account_id)})


def _order_state(self, account_id, order_id):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(self._service("orders").get_order_state(account_id=str(account_id), order_id=str(order_id)))
    return _adapter._rest_request("SandboxService/GetSandboxOrderState", {"accountId": str(account_id), "orderId": str(order_id), "orderIdType": "ORDER_ID_TYPE_UNSPECIFIED", "priceType": "PRICE_TYPE_CURRENCY"})


def _create_order(self, payload):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(self._service("orders").post_order(quantity=int(payload["quantity"]), direction=fixed._sdk_order_direction(payload["direction"]), account_id=str(payload["account_id"]), order_type=fixed._sdk_order_type(payload["order_type"]), instrument_id=str(payload["instrument_uid"]), order_id=str(payload.get("request_id") or payload.get("order_id") or uuid.uuid4()), price=_adapter._sdk_quotation(payload["price"]) if payload.get("price") is not None else None))
    direction = str(payload["direction"]).upper()
    direction = "ORDER_DIRECTION_BUY" if "BUY" in direction else "ORDER_DIRECTION_SELL" if "SELL" in direction else direction
    order_type = str(payload["order_type"]).upper()
    order_type = "ORDER_TYPE_MARKET" if "MARKET" in order_type else "ORDER_TYPE_LIMIT" if "LIMIT" in order_type else "ORDER_TYPE_BESTPRICE" if "BEST" in order_type else order_type
    instrument_id = str(payload.get("instrument_uid") or payload.get("instrument_id") or "")
    if not instrument_id: raise ValueError("instrument_uid/instrument_id is required")
    request = {"quantity": str(int(payload["quantity"])), "direction": direction, "accountId": str(payload["account_id"]), "orderType": order_type, "orderId": str(payload.get("request_id") or payload.get("order_id") or uuid.uuid4()), "instrumentId": instrument_id, "timeInForce": str(payload.get("time_in_force") or "TIME_IN_FORCE_DAY"), "priceType": str(payload.get("price_type") or "PRICE_TYPE_CURRENCY"), "confirmMarginTrade": bool(payload.get("confirm_margin_trade", False))}
    if payload.get("price") is not None: request["price"] = _adapter._quotation_payload(payload["price"])
    return self._rest_request("SandboxService/PostSandboxOrder", request)


def _cancel_order(self, account_id, order_id):
    if _adapter.ENVIRONMENT != "sandbox": return _adapter.message_to_dict(self._service("orders").cancel_order(account_id=str(account_id), order_id=str(order_id)))
    return self._rest_request("SandboxService/CancelSandboxOrder", {"accountId": str(account_id), "orderId": str(order_id), "orderIdType": "ORDER_ID_TYPE_UNSPECIFIED"})


def _replace_order(self, payload):
    order_id = str(payload.get("order_id") or "")
    account_id = str(payload.get("account_id") or "")
    quantity = int(payload.get("quantity") or 0)
    if not order_id or not account_id or quantity <= 0: raise ValueError("account_id, order_id and positive quantity are required")
    if _adapter.ENVIRONMENT != "sandbox":
        kwargs = {"order_id": order_id, "quantity": quantity, "account_id": account_id}
        if payload.get("price") is not None: kwargs["price"] = _adapter._sdk_quotation(payload["price"])
        return _adapter.message_to_dict(self._service("orders").replace_order(**kwargs))
    request = {"accountId": account_id, "orderIdType": "ORDER_ID_TYPE_UNSPECIFIED", "orderId": order_id, "idempotencyKey": str(payload.get("request_id") or payload.get("idempotency_key") or uuid.uuid4()), "quantity": str(quantity), "priceType": str(payload.get("price_type") or "PRICE_TYPE_CURRENCY"), "confirmMarginTrade": bool(payload.get("confirm_margin_trade", False))}
    if payload.get("price") is not None: request["price"] = _adapter._quotation_payload(payload["price"])
    return self._rest_request("SandboxService/ReplaceSandboxOrder", request)


def _create_stop_order(self, payload):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(self._service("stop_orders").post_stop_order(**payload))
    direction = str(payload.get("direction") or "").upper()
    direction = "STOP_ORDER_DIRECTION_BUY" if "BUY" in direction else "STOP_ORDER_DIRECTION_SELL" if "SELL" in direction else direction
    instrument_id = str(payload.get("instrument_uid") or payload.get("instrument_id") or "")
    if not instrument_id: raise ValueError("instrument_uid/instrument_id is required")
    request = {"quantity": str(int(payload["quantity"])), "direction": direction, "accountId": str(payload["account_id"]), "instrumentId": instrument_id, "stopPrice": _adapter._quotation_payload(payload["stop_price"]), "stopOrderType": str(payload.get("stop_order_type") or "STOP_ORDER_TYPE_STOP_LOSS"), "expirationType": str(payload.get("expiration_type") or "STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL"), "exchangeOrderType": str(payload.get("exchange_order_type") or "EXCHANGE_ORDER_TYPE_MARKET"), "takeProfitType": str(payload.get("take_profit_type") or "TAKE_PROFIT_TYPE_UNSPECIFIED"), "priceType": str(payload.get("price_type") or "PRICE_TYPE_CURRENCY"), "orderId": str(payload.get("order_id") or uuid.uuid4())}
    if payload.get("price") is not None: request["price"] = _adapter._quotation_payload(payload["price"])
    return self._rest_request("SandboxService/PostSandboxStopOrder", request)


def _stop_orders(self, account_id):
    if _adapter.ENVIRONMENT != "sandbox": return _adapter.message_to_dict(self._service("stop_orders").get_stop_orders(account_id=str(account_id)))
    return self._rest_request("SandboxService/GetSandboxStopOrders", {"accountId": str(account_id)})


def _cancel_stop_order(self, account_id, stop_order_id):
    if _adapter.ENVIRONMENT != "sandbox": return _adapter.message_to_dict(self._service("stop_orders").cancel_stop_order(account_id=str(account_id), stop_order_id=str(stop_order_id)))
    return self._rest_request("SandboxService/CancelSandboxStopOrder", {"accountId": str(account_id), "stopOrderId": str(stop_order_id)})


_adapter.AdapterState.operations = _operations
_adapter.AdapterState.orders = _orders
_adapter.AdapterState.order_state = _order_state
_adapter.AdapterState.create_order = _create_order
_adapter.AdapterState.cancel_order = _cancel_order
_adapter.AdapterState.replace_order = _replace_order
_adapter.AdapterState.post_stop_order = _create_stop_order
_adapter.AdapterState.get_stop_orders = _stop_orders
_adapter.AdapterState.cancel_stop_order = _cancel_stop_order

tinvest_candles_patch.install(_adapter)

import tinvest_multifactor_patch_v081

tinvest_multifactor_patch_v081.install()

if __name__ == "__main__": _adapter.main()
