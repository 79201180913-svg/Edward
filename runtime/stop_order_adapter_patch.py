from __future__ import annotations

from typing import Any


def _direction(value: Any) -> str:
    raw = str(getattr(value, "value", value)).upper()
    if raw in {"BUY", "STOP_ORDER_DIRECTION_BUY"}:
        return "STOP_ORDER_DIRECTION_BUY"
    if raw in {"SELL", "STOP_ORDER_DIRECTION_SELL"}:
        return "STOP_ORDER_DIRECTION_SELL"
    raise ValueError(f"Unsupported stop order direction: {value!r}")


def _stop_type(value: Any) -> str:
    raw = str(getattr(value, "value", value)).upper()
    mapping = {
        "STOP_LOSS": "STOP_ORDER_TYPE_STOP_LOSS",
        "STOP_ORDER_TYPE_STOP_LOSS": "STOP_ORDER_TYPE_STOP_LOSS",
        "TAKE_PROFIT": "STOP_ORDER_TYPE_TAKE_PROFIT",
        "STOP_ORDER_TYPE_TAKE_PROFIT": "STOP_ORDER_TYPE_TAKE_PROFIT",
    }
    try:
        return mapping[raw]
    except KeyError as exc:
        raise ValueError(f"Unsupported stop order type: {value!r}") from exc


def install(adapter_module: Any) -> None:
    if getattr(adapter_module, "_stop_order_patch_installed", False):
        return

    def create_stop_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = {
            "quantity": str(int(payload["quantity"])),
            "direction": _direction(payload["direction"]),
            "accountId": str(payload["account_id"]),
            "expirationType": str(payload.get("expiration_type", "STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL")),
            "stopOrderType": _stop_type(payload["stop_order_type"]),
            "instrumentId": str(payload["instrument_uid"] if payload.get("instrument_uid") else payload["instrument_id"]),
            "orderId": str(payload["order_id"]),
        }
        if payload.get("stop_price") is not None:
            request["stopPrice"] = adapter_module._quotation_payload(payload["stop_price"])
        if payload.get("price") is not None:
            request["price"] = adapter_module._quotation_payload(payload["price"])
        request["exchangeOrderType"] = str(payload.get("exchange_order_type", "EXCHANGE_ORDER_TYPE_MARKET"))
        request["priceType"] = str(payload.get("price_type", "PRICE_TYPE_CURRENCY"))
        if payload.get("take_profit_type"):
            request["takeProfitType"] = str(payload["take_profit_type"])
        if payload.get("expire_date"):
            request["expireDate"] = str(payload["expire_date"])
        if payload.get("confirm_margin_trade") is not None:
            request["confirmMarginTrade"] = bool(payload["confirm_margin_trade"])
        method = "SandboxService/PostSandboxStopOrder" if adapter_module.ENVIRONMENT == "sandbox" else "StopOrdersService/PostStopOrder"
        return self._rest_request(method, request)

    def get_stop_orders(self, account_id: str) -> dict[str, Any]:
        method = "SandboxService/GetSandboxStopOrders" if adapter_module.ENVIRONMENT == "sandbox" else "StopOrdersService/GetStopOrders"
        return self._rest_request(
            method,
            {
                "accountId": str(account_id),
                "status": "STOP_ORDER_STATUS_ACTIVE",
            },
        )

    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> dict[str, Any]:
        method = "SandboxService/CancelSandboxStopOrder" if adapter_module.ENVIRONMENT == "sandbox" else "StopOrdersService/CancelStopOrder"
        return self._rest_request(
            method,
            {"accountId": str(account_id), "stopOrderId": str(stop_order_id)},
        )

    adapter_module.AdapterState.create_stop_order = create_stop_order
    adapter_module.AdapterState.get_stop_orders = get_stop_orders
    adapter_module.AdapterState.cancel_stop_order = cancel_stop_order

    original_do_post = adapter_module.Handler.do_POST

    def do_post(self: Any) -> None:
        if self.path in {"/stop-orders/create", "/stop-orders" , "/stop-orders/cancel"}:
            payload = self._read_json()
            if self.path == "/stop-orders/create":
                result = adapter_module.STATE.create_stop_order(payload)
            elif self.path == "/stop-orders":
                result = adapter_module.STATE.get_stop_orders(str(payload["account_id"]))
            else:
                result = adapter_module.STATE.cancel_stop_order(str(payload["account_id"]), str(payload["stop_order_id"]))
            self._send(200, result)
            return
        original_do_post(self)

    adapter_module.Handler.do_POST = do_post
    adapter_module._stop_order_patch_installed = True
