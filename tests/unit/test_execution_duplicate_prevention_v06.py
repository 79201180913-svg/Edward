from types import SimpleNamespace

from edward.domain.execution import ExecutionStatus
from edward.services.execution_bridge_service_v06 import ExecutionBridgeService
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine
from edward.services.execution_queue_action_v06 import ExecutionQueueActionController


class FakeAdapter:
    def submit(self, request):
        return "broker-1"

    def cancel(self, broker_order_id):
        return None

    def get_status(self, broker_order_id):
        raise AssertionError("status is not queried in this test")


class FakeValidator:
    def validate(self, request):
        return True, ()


def result():
    return SimpleNamespace(
        instrument_uid="uid-1",
        ticker="RZSB",
        decision="REDUCE",
        execution_ready=True,
        recommended_quantity=100,
        price=34.6,
        strategy_name="Trend",
        strategy_score=41.6,
        opportunity_score=0.0,
        risk_score=79.8,
        trade_plan=SimpleNamespace(entry_price=34.6, stop_price=37.09),
    )


def bridge():
    service = ControlledExecutionService(
        ExecutionEngine(adapter=FakeAdapter()),
        FakeValidator(),
    )
    return ExecutionBridgeService(service)


def test_duplicate_active_execution_is_rejected_without_creating_new_journal_entry():
    execution_bridge = bridge()
    first = execution_bridge.enqueue_opportunity(account_id="acc-1", result=result())
    second = execution_bridge.enqueue_opportunity(account_id="acc-1", result=result())

    assert first.accepted is True
    assert second.accepted is False
    assert second.reason == "Заявка уже передана в исполнение"
    assert len(execution_bridge.all()) == 1
    assert first.request.execution_id == second.request.execution_id


def test_queue_action_reports_already_submitted_state():
    execution_bridge = bridge()
    controller = ExecutionQueueActionController(
        bridge=execution_bridge,
        account_id_provider=lambda: "acc-1",
    )
    opportunity = result()

    assert controller.status_text(opportunity) == "Готово к передаче в исполнение"
    controller.enqueue(opportunity)
    assert controller.is_already_queued(opportunity) is True
    assert controller.status_text(opportunity) == "Уже передано в исполнение"


def test_duplicate_guard_only_applies_to_non_terminal_items():
    execution_bridge = bridge()
    first = execution_bridge.enqueue_opportunity(account_id="acc-1", result=result())
    assert first.accepted is True

    execution_bridge._items[first.request.execution_id] = execution_bridge._items[first.request.execution_id].__class__(
        request=first.request,
        result=first.result.__class__(
            execution_id=first.result.execution_id,
            status=ExecutionStatus.CANCELLED,
        ),
    )

    assert execution_bridge.has_active_opportunity(account_id="acc-1", result=result()) is False
