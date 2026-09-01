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


def _get_instrument(self, instrument_id):
    """Contract-correct GetInstrumentBy using UID identification."""
    instrument_id = str(instrument_id or "")
    if not instrument_id:
        raise ValueError("instrument_id is required")
    result = self._rest_request(
        "InstrumentsService/GetInstrumentBy",
        {
            "idType": "INSTRUMENT_ID_TYPE_UID",
            "id": instrument_id,
        },
    )
    instrument = result.get("instrument") if isinstance(result, dict) else None
    risk_fields = {}
    if isinstance(instrument, dict):
        for key in ("dlong", "dshort", "dlong_min", "dshort_min", "dlong_client", "dshort_client", "short_enabled_flag"):
            risk_fields[key] = instrument.get(key)
    _adapter.logger.info(
        "[INSTRUMENT LOOKUP] instrument_uid=%s found=%s keys=%s risk_fields=%s",
        instrument_id,
        bool(result),
        list(result.keys()) if isinstance(result, dict) else type(result).__name__,
        risk_fields,
    )
    return result


def _find_instrument(self, query, trade=True, instrument_kind="INSTRUMENT_TYPE_UNSPECIFIED"):
    """Contract-correct InstrumentsService.FindInstrument bridge.

    The local HTTP adapter must forward the search to the actual T-Invest API;
    otherwise a local 404 would be indistinguishable from a broker response.
    """
    query = str(query or "").strip()
    if not query:
        raise ValueError("query is required")
    payload = {
        "query": query,
        "instrumentKind": str(instrument_kind or "INSTRUMENT_TYPE_UNSPECIFIED"),
        "apiTradeAvailableFlag": bool(trade),
    }
    result = self._rest_request("InstrumentsService/FindInstrument", payload)
    _adapter.logger.info(
        "[INSTRUMENT SEARCH] query=%s kind=%s trade_available=%s results=%s",
        query,
        payload["instrumentKind"],
        payload["apiTradeAvailableFlag"],
        len(result.get("instruments", []) or []) if isinstance(result, dict) else 0,
    )
    return result


def _indicatives(self):
    """Contract-correct InstrumentsService.Indicatives bridge."""
    result = self._rest_request("InstrumentsService/Indicatives", {})
    _adapter.logger.info(
        "[INDICATIVES] results=%s",
        len(result.get("instruments", []) or []) if isinstance(result, dict) else 0,
    )
    return result


_adapter.AdapterState.operations = _operations
_adapter.AdapterState.orders = _orders
_adapter.AdapterState.order_state = _order_state
_adapter.AdapterState.create_order = _create_order
_adapter.AdapterState.cancel_order = _cancel_order
_adapter.AdapterState.replace_order = _replace_order
_adapter.AdapterState.post_stop_order = _create_stop_order
_adapter.AdapterState.get_stop_orders = _stop_orders
_adapter.AdapterState.cancel_stop_order = _cancel_stop_order
_adapter.AdapterState.get_instrument = _get_instrument
_adapter.AdapterState.find_instrument = _find_instrument
_adapter.AdapterState.get_indicatives = _indicatives

_original_handler_do_post = _adapter.Handler.do_POST


def _handler_do_post(self):
    if self.path == "/instruments/get":
        try:
            payload = self._read_json()
            result = _adapter.STATE.get_instrument(str(payload.get("instrument_id") or payload.get("id") or ""))
            self._send(200, result)
            return
        except Exception as exc:
            _adapter.logger.exception("[INSTRUMENT LOOKUP ERROR] %s", exc)
            self._send(500, {"error": str(exc), "type": type(exc).__name__})
            return
    if self.path == "/instruments/search":
        try:
            payload = self._read_json()
            result = _adapter.STATE.find_instrument(
                str(payload.get("query") or ""),
                bool(payload.get("api_trade_available_flag", True)),
                str(payload.get("instrument_kind") or "INSTRUMENT_TYPE_UNSPECIFIED"),
            )
            self._send(200, result)
            return
        except Exception as exc:
            _adapter.logger.exception("[INSTRUMENT SEARCH ERROR] %s", exc)
            self._send(500, {"error": str(exc), "type": type(exc).__name__})
            return
    if self.path == "/instruments/indicatives":
        try:
            result = _adapter.STATE.get_indicatives()
            self._send(200, result)
            return
        except Exception as exc:
            _adapter.logger.exception("[INDICATIVES ERROR] %s", exc)
            self._send(500, {"error": str(exc), "type": type(exc).__name__})
            return
    return _original_handler_do_post(self)


_adapter.Handler.do_POST = _handler_do_post

tinvest_candles_patch.install(_adapter)

import tinvest_multifactor_patch_v081

tinvest_multifactor_patch_v081.install()

if __name__ == "__main__": _adapter.main()