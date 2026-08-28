from decimal import Decimal

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan
from edward.services.autonomous_trading_controller import AutonomousTradingController
from edward.services.budget_planning_service import BudgetPlan


class SequenceDouble:
    def __init__(self):
        self.calls = []

    def execute_confirmed_plan(self, **kwargs):
        self.calls.append(kwargs)
        verification = type("Verification", (), {"passed": True, "reasons": ()})()
        step_result = type("StepResult", (), {"completed": True, "reason": "", "verification": verification})()
        return type("Sequence", (), {"completed": True, "stopped_at": None, "steps": (step_result,)})()


def budget(value):
    return BudgetPlan(
        account_capital=value,
        cash=value,
        blocked_cash=Decimal("0"),
        invested=Decimal("0"),
        reserve=Decimal("0"),
        planning_budget=value,
        investable_cash=value,
        slots=5,
        target_position_value=value,
    )


def test_replanned_execution_recalculates_budget_from_live_state_before_step():
    sequence = SequenceDouble()
    controller = AutonomousTradingController(sequence)
    controller.enable()

    initial = AccountState(portfolio=None, positions=[], balance=None, orders=[])
    after_refresh = AccountState(portfolio=None, positions=[{"instrument_uid": "released", "quantity": 0}], balance=None, orders=[])
    after_fill = AccountState(portfolio=None, positions=[{"instrument_uid": "new", "quantity": 10}], balance=None, orders=[])
    states = [initial, after_refresh, after_fill]
    observed_budget_states = []

    step = type("Step", (), {
        "sequence": 1,
        "action": "BUY",
        "instrument_uid": "new",
        "target_value": Decimal("10000"),
        "depends_on": None,
    })()
    plan = AutonomousExecutionPlan(steps=(step,))

    def refresh_state():
        return states.pop(0)

    def budget_for_state(state):
        observed_budget_states.append(state)
        return budget(Decimal("25000"))

    result = controller.execute_replanned(
        account_id="ACC",
        mode=ExecutionMode.AUTONOMOUS,
        refresh_state=refresh_state,
        build_plan=lambda _state: plan,
        budget_for_state=budget_for_state,
        result_factory=lambda _step: type("Opportunity", (), {
            "decision": "BUY",
            "execution_ready": True,
            "instrument_uid": "new",
            "ticker": "NEW",
            "recommended_quantity": 10,
            "price": Decimal("1000"),
        })(),
        max_iterations=1,
    )

    assert result.executed is True
    assert len(observed_budget_states) == 2
    assert observed_budget_states[0] is initial
    assert observed_budget_states[1] is after_refresh
    assert sequence.calls[0]["initial_state"] is after_refresh
