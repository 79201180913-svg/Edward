from types import SimpleNamespace

import pytest

from edward.domain.execution import ExecutionDecision
from edward.services.execution_request_factory_v06 import build_execution_request


def result(decision="BUY", ready=True, quantity=10):
    return SimpleNamespace(
        instrument_uid="uid-1",
        ticker="TEST",
        decision=decision,
        execution_ready=ready,
        recommended_quantity=quantity,
        price=100.0,
        strategy_name="Trend",
        strategy_score=80.0,
        opportunity_score=75.0,
        risk_score=12.0,
        trade_plan=SimpleNamespace(entry_price=101.0, stop_price=95.0),
    )


def test_factory_maps_buy_to_buy_limit_request():
    request = build_execution_request(account_id="acc-1", result=result("BUY"))
    assert request.decision is ExecutionDecision.BUY
    assert request.side == "BUY"
    assert request.quantity == 10
    assert request.order_type == "LIMIT"
    assert request.entry_price == 101
    assert request.stop_price == 95
    assert request.execution_ready is True


def test_factory_maps_reduce_to_sell_request():
    request = build_execution_request(account_id="acc-1", result=result("REDUCE", quantity=7))
    assert request.decision is ExecutionDecision.REDUCE
    assert request.side == "SELL"
    assert request.quantity == 7


@pytest.mark.parametrize("decision", ["WAIT", "HOLD", "PASS", ""])
def test_factory_rejects_non_executable_decisions(decision):
    with pytest.raises(ValueError, match="decision is not executable"):
        build_execution_request(account_id="acc-1", result=result(decision))


def test_factory_rejects_not_ready_and_zero_quantity():
    with pytest.raises(ValueError, match="execution_ready=True"):
        build_execution_request(account_id="acc-1", result=result(ready=False))
    with pytest.raises(ValueError, match="positive recommended_quantity"):
        build_execution_request(account_id="acc-1", result=result(quantity=0))
