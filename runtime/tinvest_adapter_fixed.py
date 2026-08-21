from __future__ import annotations

from datetime import datetime, timedelta, timezone

import tinvest_adapter as _adapter


def _sandbox_positions(self, account_id):
    result = self._rest_request(
        "SandboxService/GetSandboxPositions",
        {"accountId": str(account_id)},
    )
    _adapter.logger.info(
        "[SANDBOX POSITIONS REST] account_id=%s securities=%s money=%s",
        account_id,
        len(result.get("securities", []) or []),
        len(result.get("money", []) or []),
    )
    return result


def _sandbox_portfolio(self, account_id):
    result = self._rest_request(
        "SandboxService/GetSandboxPortfolio",
        {"accountId": str(account_id), "currency": "RUB"},
    )
    _adapter.logger.info(
        "[SANDBOX PORTFOLIO REST] account_id=%s positions=%s total=%s",
        account_id,
        len(result.get("positions", []) or []),
        result.get("total_amount_portfolio"),
    )
    return result


def _sandbox_operations(self, account_id, limit=1000):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=3650)
    payload = {
        "accountId": str(account_id),
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
        "limit": max(1, min(int(limit), 1000)),
        "withoutCommissions": False,
        "withoutTrades": False,
        "withoutOvernights": False,
    }
    result = self._rest_request(
        "SandboxService/GetSandboxOperationsByCursor",
        payload,
    )
    items = result.get("items", []) or []
    _adapter.logger.info(
        "[SANDBOX OPERATIONS REST] account_id=%s items=%s",
        account_id,
        len(items),
    )
    if items:
        _adapter.logger.info("[SANDBOX OPERATION SAMPLE] %s", items[0])
    return result


_adapter.AdapterState.sandbox_positions = _sandbox_positions
_adapter.AdapterState.sandbox_portfolio = _sandbox_portfolio
_adapter.AdapterState.operations = _sandbox_operations


if __name__ == "__main__":
    _adapter.main()
