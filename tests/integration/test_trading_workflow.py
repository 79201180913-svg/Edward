import pytest

from edward.services.execution_service import ExecutionContext
from edward.services.order_service import OrderRequest, OrderSide, OrderType
from edward.services.trading_workflow import TradingWorkflow


class FakeSubmission:
    def submit(self, request):
        return {"order_id": "order-1"}


class FakeMonitor:
    def wait_for_terminal(self, account_id, order_id, interval_seconds, timeout_seconds):
        from edward.domain.order_state import OrderSnapshot, OrderStatus
        return OrderSnapshot(order_id, account_id, "uid-1", OrderStatus.FILLED, 1, 1, 0)


class FakeRefresh:
    def refresh(self, account_id):
        return {"account_id": account_id, "balance": "refreshed"}


class FakeExecution:
    def __init__(self):
        self.processed = False

    def process(self, snapshot, context):
        self.processed = True


def test_workflow():
    execution = FakeExecution()
    workflow = TradingWorkflow(FakeSubmission(), FakeMonitor(), FakeRefresh(), execution)
    request = OrderRequest("acc", "uid-1", OrderSide.BUY, OrderType.MARKET, 1)
    result = workflow.execute(request, ExecutionContext(operation="BUY"), timeout_seconds=2)
    assert result.order_id == "order-1"
    assert execution.processed is True
    assert result.refreshed_state["balance"] == "refreshed"
