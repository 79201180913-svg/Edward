from decimal import Decimal

from edward.domain.execution import ExecutionDecision, ExecutionRequest
from edward.services.execution_center_controller_v06 import ExecutionCenterController
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine


class FakeAdapter:
    def submit(self, request):
        return "broker-1"

    def cancel(self, broker_order_id):
        pass

    def get_status(self, broker_order_id):
        raise AssertionError("not used")


class FakeValidator:
    def validate(self, request):
        return True, ()


def request():
    return ExecutionRequest(
        execution_id="stale-ui-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=Decimal("1"),
        order_type="LIMIT",
        entry_price=Decimal("100"),
        execution_ready=True,
    )


def service():
    return ControlledExecutionService(ExecutionEngine(adapter=FakeAdapter()), FakeValidator())


def test_stale_ui_callback_is_detached_after_callback_failure():
    calls = []

    def stale_callback(state):
        calls.append(state.status)
        raise RuntimeError("invalid command name .!toplevel.!frame.!russiantreeview")

    controller = ExecutionCenterController(service(), on_change=stale_callback)
    controller.load_request(request())

    assert calls
    assert controller.on_change is None

    # Later publications must continue the execution flow without reusing the dead Tk callback.
    result = controller.prepare()
    assert result.status.value == "READY"
    assert controller.state.status.value == "READY"
    controller.close()
