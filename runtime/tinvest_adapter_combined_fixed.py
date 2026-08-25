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


_adapter.AdapterState.operations = _operations
_adapter.AdapterState.orders = _orders


if __name__ == "__main__":
    _adapter.main()
