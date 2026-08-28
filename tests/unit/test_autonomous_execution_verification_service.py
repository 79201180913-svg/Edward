from types import SimpleNamespace

from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import ExecutionPlanStep
from edward.services.autonomous_execution_verification_service import (
    AutonomousExecutionVerificationService,
)


def step(action="BUY", uid="uid-1"):
    return ExecutionPlanStep(
        sequence=1,
        action=action,
        ticker="TEST",
        instrument_uid=uid,
        target_value=10000,
    )


def state(quantity=10, uid="uid-1"):
    return AccountState(
        portfolio=None,
        positions=[SimpleNamespace(instrument_uid=uid, quantity=quantity)],
        balance=None,
        orders=None,
    )


def test_buy_is_verified_from_refreshed_position():
    result = AutonomousExecutionVerificationService().verify(
        step=step(), state=state(10), expected_quantity=10,
    )
    assert result.passed is True
    assert result.actual_quantity == 10


def test_buy_against_existing_position_uses_quantity_delta():
    result = AutonomousExecutionVerificationService().verify(
        step=step(), state=state(15), expected_quantity=5, before_quantity=10,
    )
    assert result.passed is True


def test_buy_is_rejected_when_position_not_reached():
    result = AutonomousExecutionVerificationService().verify(
        step=step(), state=state(14), expected_quantity=5, before_quantity=10,
    )
    assert result.passed is False
    assert "POSITION_QUANTITY_NOT_REACHED" in result.reasons[0]


def test_sell_requires_zero_position():
    result = AutonomousExecutionVerificationService().verify(
        step=step("SELL"), state=state(0), expected_quantity=10, before_quantity=10,
    )
    assert result.passed is True


def test_reduce_requires_order_quantity_reduction():
    result = AutonomousExecutionVerificationService().verify(
        step=step("REDUCE"), state=state(6), expected_quantity=4, before_quantity=10,
    )
    assert result.passed is True


def test_reduce_is_rejected_when_quantity_did_not_decrease_enough():
    result = AutonomousExecutionVerificationService().verify(
        step=step("REDUCE"), state=state(7), expected_quantity=4, before_quantity=10,
    )
    assert result.passed is False
    assert "POSITION_NOT_REDUCED_ENOUGH" in result.reasons[0]


def test_zero_expected_quantity_is_invalid():
    result = AutonomousExecutionVerificationService().verify(
        step=step(), state=state(10), expected_quantity=0,
    )
    assert result.passed is False
    assert result.reasons == ("INVALID_EXPECTED_QUANTITY",)
