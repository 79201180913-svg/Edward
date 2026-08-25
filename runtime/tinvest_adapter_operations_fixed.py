from __future__ import annotations

"""Canonical Sandbox operations adapter.

The existing tinvest_adapter_fixed.py overrides AdapterState.operations with the
legacy get_sandbox_operations alias. In the installed SDK that alias returns an
incompatible payload. The base adapter already contains the correct REST
implementation for GetSandboxOperationsByCursor, so this wrapper imports the
existing adapter and restores that implementation before starting the server.
"""

import tinvest_adapter_fixed as fixed

_adapter = fixed._adapter


def _operations(self, account_id, limit=1000):
    if _adapter.ENVIRONMENT != "sandbox":
        return _adapter.message_to_dict(
            self._service("operations").get_operations_by_cursor(
                account_id=str(account_id),
                limit=max(1, min(int(limit), 1000)),
                without_commissions=False,
                without_trades=False,
            )
        )

    return self._rest_request(
        "SandboxService/GetSandboxOperationsByCursor",
        {
            "accountId": str(account_id),
            "limit": max(1, min(int(limit), 1000)),
            "withoutCommissions": False,
            "withoutTrades": False,
        },
    )


_adapter.AdapterState.operations = _operations


if __name__ == "__main__":
    _adapter.main()
