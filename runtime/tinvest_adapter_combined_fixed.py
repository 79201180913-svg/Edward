from __future__ import annotations

"""Canonical Sandbox adapter combining the fixed orders and operations contracts."""

import tinvest_adapter_fixed as fixed

_adapter = fixed._adapter


def _operations(self, account_id, limit=1000):
    limit = max(1, min(int(limit), 1000))
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(
            self._service("operations").get_operations_by_cursor(
                account_id=str(account_id),
                limit=limit,
                without_commissions=False,
                without_trades=False,
            )
        )

    return self._rest_request(
        "SandboxService/GetSandboxOperationsByCursor",
        {
            "accountId": str(account_id),
            "limit": limit,
            "withoutCommissions": False,
            "withoutTrades": False,
        },
    )


def _orders(self, account_id):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(
            self._service("orders").get_orders(account_id=str(account_id))
        )

    return self._rest_request(
        "SandboxService/GetSandboxOrders",
        {"accountId": str(account_id)},
    )


def _order_state(self, account_id, order_id):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(
            self._service("orders").get_order_state(
                account_id=str(account_id),
                order_id=str(order_id),
            )
        )

    return self._rest_request(
        "SandboxService/GetSandboxOrderState",
        {
            "accountId": str(account_id),
            "orderId": str(order_id),
            "orderIdType": "ORDER_ID_TYPE_UNSPECIFIED",
            "priceType": "PRICE_TYPE_CURRENCY",
        },
    )


def _replace_order(self, payload):
    order_id = str(payload.get("order_id") or "")
    account_id = str(payload.get("account_id") or "")
    if not order_id:
        raise ValueError("order_id is required")
    if not account_id:
        raise ValueError("account_id is required")

    quantity = int(payload.get("quantity") or 0)
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    request = {
        "accountId": account_id,
        "orderIdType": "ORDER_ID_TYPE_UNSPECIFIED",
        "orderId": order_id,
        "idempotencyKey": str(payload.get("request_id") or payload.get("idempotency_key") or order_id),
        "quantity": str(quantity),
        "priceType": str(payload.get("price_type") or "PRICE_TYPE_CURRENCY"),
        "confirmMarginTrade": bool(payload.get("confirm_margin_trade", False)),
    }
    if payload.get("price") is not None:
        request["price"] = _adapter._quotation_payload(payload["price"])

    if _adapter.ENVIRONMENT != "sandbox":
        kwargs = {
            "order_id": order_id,
            "quantity": quantity,
            "account_id": account_id,
        }
        if payload.get("price") is not None:
            kwargs["price"] = _adapter._sdk_quotation(payload["price"])
        return _adapter.message_to_dict(
            self._service("orders").replace_order(**kwargs)
        )

    return self._rest_request("SandboxService/ReplaceSandboxOrder", request)


_adapter.AdapterState.operations = _operations
_adapter.AdapterState.orders = _orders
_adapter.AdapterState.order_state = _order_state
_adapter.AdapterState.replace_order = _replace_order


if __name__ == "__main__":
    _adapter.main()
