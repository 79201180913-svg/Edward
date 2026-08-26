from types import SimpleNamespace

from edward.services.execution_opportunity_registry_v06 import ExecutionOpportunityRegistry
from edward.services.execution_queue_action_v06 import can_enqueue_opportunity, enqueue_button_text


def opportunity(*, ready=True, quantity=10, decision="BUY"):
    return SimpleNamespace(
        ticker="TEST",
        instrument_uid="uid-1",
        decision=decision,
        execution_ready=ready,
        recommended_quantity=quantity,
    )


def test_ready_opportunity_exposes_transfer_action():
    item = opportunity()
    assert can_enqueue_opportunity(item) is True
    assert enqueue_button_text(item) == "Передать в исполнение"


def test_blocked_opportunity_disables_transfer_action():
    item = opportunity(ready=False)
    assert can_enqueue_opportunity(item) is False
    assert enqueue_button_text(item) == "Исполнение недоступно"


def test_registry_resolves_selected_ticker():
    registry = ExecutionOpportunityRegistry()
    registry.add(opportunity())
    assert registry.get("TEST") is not None
    assert registry.get("uid-1").ticker == "TEST"
