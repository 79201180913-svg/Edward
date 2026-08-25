from __future__ import annotations

"""Canonical Sandbox orders adapter.

The installed SDK response conversion in tinvest_adapter_fixed.py does not expose
all order fields needed by the UI (direction, order type, execution status).
For Sandbox orders we therefore restore the REST contract directly, preserving
all fields returned by GetSandboxOrders.
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


_adapter.AdapterState.orders = _orders


if __name__ == "__main__":
    _adapter.main()
