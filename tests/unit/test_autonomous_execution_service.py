from decimal import Decimal
from types import SimpleNamespace

import pytest

from edward.services.autonomous_execution_service import AutonomousExecutionService
from edward.services.autonomous_execution_plan_service import ExecutionPlanStep


class FakeBridge:
    def __init__(self):
        self.calls = []

    def enqueue_opportunity(self, *, account_id, result):
        self.calls.append((account_id, result))
        return "accepted"


def step(action="BUY", ticker="TEST", uid="uid-1", depends_on=None):
    return ExecutionPlanStep(
        sequence=1,
        action=action,
        ticker=ticker,
        instrument_uid=uid,
        target_value=Decimal("10000"),
        depends_on=depends_on,
    )


def result(**overrides):
    values = {
        "decision": "BUY",
        "execution_ready": True,
        "recommended_quantity": 10,
        "instrument_uid": "uid-1",
        "ticker": "TEST",
        "price": 100.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_matching_fresh_result_is_valid():
    service = AutonomousExecutionService(FakeBridge())
    validation = service.validate_step(step=step(), result=result())
    assert validation.passed is True
    assert validation.reasons == ()


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"execution_ready": False}, "EXECUTION_NOT_READY"),
        ({"instrument_uid": "other"}, "INSTRUMENT_UID_MISMATCH:other!=uid-1"),
        ({"ticker": "OTHER"}, "TICKER_MISMATCH:OTHER!=TEST"),
        ({"decision": "SELL"}, "DECISION_MISMATCH:SELL!=BUY"),
        ({"recommended_quantity": 0}, "INVALID_RECOMMENDED_QUANTITY"),
        ({"price": 0}, "INVALID_ENTRY_PRICE"),
    ],
)
def test_stale_or_invalid_result_is_rejected(overrides, expected):
    service = AutonomousExecutionService(FakeBridge())
    validation = service.validate_step(step=step(), result=result(**overrides))
    assert validation.passed is False
    assert expected in validation.reasons


def test_dependency_must_be_completed():
    service = AutonomousExecutionService(FakeBridge())
    validation = service.validate_step(
        step=step(action="BUY", depends_on=3),
        result=result(),
        dependency_completed=False,
    )
    assert validation.passed is False
    assert validation.reasons == ("DEPENDENCY_NOT_COMPLETED:3",)


def test_prepare_delegates_only_after_validation():
    bridge = FakeBridge()
    service = AutonomousExecutionService(bridge)
    returned = service.prepare_step(
        account_id="ACC",
        step=step(),
        result=result(),
    )
    assert returned == "accepted"
    assert bridge.calls == [("ACC", result())]


def test_prepare_rejects_without_calling_bridge():
    bridge = FakeBridge()
    service = AutonomousExecutionService(bridge)
    with pytest.raises(ValueError, match="EXECUTION_NOT_READY"):
        service.prepare_step(
            account_id="ACC",
            step=step(),
            result=result(execution_ready=False),
        )
    assert bridge.calls == []


def test_prepare_step_from_fresh_result_refreshes_before_intake():
    bridge = FakeBridge()
    service = AutonomousExecutionService(bridge)
    refreshed = result(price=101.5, recommended_quantity=9)
    calls = []

    def factory(planned_step):
        calls.append(planned_step)
        return refreshed

    returned = service.prepare_step_from_fresh_result(
        account_id="ACC",
        step=step(),
        result_factory=factory,
    )

    assert returned == "accepted"
    assert calls == [step()]
    assert bridge.calls == [("ACC", refreshed)]
