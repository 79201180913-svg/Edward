from decimal import Decimal

import pytest

from edward.domain.execution import ExecutionDecision, ExecutionRequest, ExecutionStatus
from edward.services.tinvest_execution_adapter import TInvestExecutionAdapter


class FakeClient:
    def __init__(self):
        self.created = []
        self.cancelled = []
        self.state = {}

    def create_order(self, payload):
        self.created.append(dict(payload))
        return {"order_id": "broker-1"}

    def order_state(self, account_id, order_id):
        return self.state[(account_id, order_id)]

    def cancel_order(self, account_id, order_id):
        self.cancelled.append((account_id, order_id))
        return {}


def request():
    return ExecutionRequest(
        execution_id="exec-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=Decimal("100"),
        order_type="LIMIT",
        entry_price=Decimal("10.25"),
        execution_ready=True,
    )


def test_submit_maps_execution_request_and_remembers_account():
    client = FakeClient()
    adapter = TInvestExecutionAdapter(client)

    broker_id = adapter.submit(request())

    assert broker_id == "broker-1"
    assert client.created == [{
        "request_id": "exec-1",
        "account_id": "acc-1",
        "instrument_uid": "uid-1",
        "direction": "BUY",
        "order_type": "LIMIT",
        "quantity": 100,
        "price": Decimal("10.25"),
    }]


def test_status_maps_partial_fill_and_quotation():
    client = FakeClient()
    adapter = TInvestExecutionAdapter(client)
    adapter.submit(request())
    client.state[("acc-1", "broker-1")] = {
        "status": "EXECUTION_REPORT_STATUS_PARTIALLYFILL",
        "lots_executed": "40",
        "executed_order_price": {"units": "10", "nano": 500000000},
        "executed_commission": {"units": "1", "nano": 250000000},
    }

    result = adapter.get_status("broker-1")

    assert result.execution_id == "exec-1"
    assert result.status == ExecutionStatus.PARTIALLY_FILLED
    assert result.filled_quantity == Decimal("40")
    assert result.average_fill_price == Decimal("10.5")
    assert result.commission == Decimal("1.25")


def test_status_maps_fill_rejected_and_cancelled():
    client = FakeClient()
    adapter = TInvestExecutionAdapter(client)
    adapter.submit(request())

    for raw, expected in (
        ("EXECUTION_REPORT_STATUS_FILL", ExecutionStatus.FILLED),
        ("EXECUTION_REPORT_STATUS_REJECTED", ExecutionStatus.REJECTED),
        ("EXECUTION_REPORT_STATUS_CANCELLED", ExecutionStatus.CANCELLED),
    ):
        client.state[("acc-1", "broker-1")] = {"status": raw, "lots_executed": "100"}
        assert adapter.get_status("broker-1").status == expected


def test_cancel_uses_account_bound_to_submission():
    client = FakeClient()
    adapter = TInvestExecutionAdapter(client)
    adapter.submit(request())

    adapter.cancel("broker-1")

    assert client.cancelled == [("acc-1", "broker-1")]


def test_unknown_broker_order_is_rejected():
    adapter = TInvestExecutionAdapter(FakeClient())

    with pytest.raises(KeyError):
        adapter.get_status("missing")

    with pytest.raises(KeyError):
        adapter.cancel("missing")


def test_submit_requires_broker_order_id():
    class NoOrderIdClient(FakeClient):
        def create_order(self, payload):
            return {"status": "ok"}

    adapter = TInvestExecutionAdapter(NoOrderIdClient())
    with pytest.raises(RuntimeError, match="broker order id"):
        adapter.submit(request())
