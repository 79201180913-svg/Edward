from decimal import Decimal
from types import SimpleNamespace

from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine
from edward.services.execution_intake_service_v06 import ExecutionIntakeService


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


def opportunity():
    return SimpleNamespace(
        decision="BUY",
        execution_ready=True,
        recommended_quantity=10,
        price=100.0,
        instrument_uid="uid-1",
        ticker="TEST",
        strategy_name="Trend",
        strategy_score=80.0,
        opportunity_score=85.0,
        risk_score=20.0,
        trade_plan=SimpleNamespace(entry_price=Decimal("100"), stop_price=Decimal("95")),
    )


def test_intake_prepares_ready_execution_request():
    service = ExecutionIntakeService(
        ControlledExecutionService(ExecutionEngine(adapter=FakeAdapter()), FakeValidator())
    )
    result = service.intake(account_id="acc-1", opportunity_result=opportunity())

    assert result.status == "READY"
    assert result.request.execution_id == "acc-1:uid-1:BUY:10"
    assert result.request.quantity == Decimal("10")


def test_intake_rejects_non_ready_opportunity():
    service = ExecutionIntakeService(
        ControlledExecutionService(ExecutionEngine(adapter=FakeAdapter()), FakeValidator())
    )
    bad = opportunity()
    bad.execution_ready = False
