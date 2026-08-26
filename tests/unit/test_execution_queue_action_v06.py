from edward.ui.execution_queue_action_v06 import can_enqueue_opportunity, enqueue_button_text


def result(*, ready=True, decision="BUY", quantity=10):
    return type("Opportunity", (), {
        "execution_ready": ready,
        "decision": decision,
        "recommended_quantity": quantity,
    })()


def test_ready_buy_can_be_sent_to_execution_queue():
    assert can_enqueue_opportunity(result()) is True
    assert enqueue_button_text(result()) == "Передать в исполнение"


def test_blocked_result_cannot_be_sent_to_execution_queue():
    assert can_enqueue_opportunity(result(ready=False)) is False
    assert enqueue_button_text(result(ready=False)) == "Исполнение недоступно"


def test_zero_quantity_cannot_be_sent_to_execution_queue():
    assert can_enqueue_opportunity(result(quantity=0)) is False


def test_non_executable_decision_cannot_be_sent_to_execution_queue():
    assert can_enqueue_opportunity(result(decision="PASS")) is False
