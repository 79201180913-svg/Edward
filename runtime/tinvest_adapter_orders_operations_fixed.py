from __future__ import annotations

"""Canonical Sandbox orders + operations adapter.

The legacy SDK aliases used by the base adapter expose incomplete/incompatible
payloads for the current UI. Keep the existing adapter implementation for all
other endpoints, while routing Sandbox orders and operations through the REST
contracts directly so all required fields are preserved.
"""

import tinvest_adapter_fixed as fixed

_adapter = fixed._adapter


def _orders(self, account_id):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(
            self._service("orders").get_orders(account_id=str(account_id))
        )
    return self._rest_request(
        "SandboxService/GetSandboxOrders",
        {"accountId": str(account_id)},
    )


def _operations(self, account_id, limit=1000):
    safe_limit = max(1, min(int(limit), 1000))
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(
            self._service("operations").get_operations_by_cursor(
                account_id=str(account_id),
                limit=safe_limit,
                without_commissions=False,
                without_trades=False,
            )
        )
    return self._rest_request(
        "SandboxService/GetSandboxOperationsByCursor",
        {
            "accountId": str(account_id),
            "limit": safe_limit,
            "withoutCommissions": False,
            "withoutTrades": False,
        },
    )


_adapter.AdapterState.orders = _orders
_adapter.AdapterState.operations = _operations


if __name__ == "__main__":
    _adapter.main()
