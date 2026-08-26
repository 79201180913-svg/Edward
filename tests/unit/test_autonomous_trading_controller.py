from decimal import Decimal
from types import SimpleNamespace

from edward.domain.execution import ExecutionMode
from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_execution_verification_service import ExecutionVerification
from edward.services.autonomous_trading_controller import AutonomousTradingController
from edward.services.budget_planning_service import BudgetPlan


class FakeSequence:
    def __init__(self):
        self.calls = []

    def execute_confirmed_plan(self, **kwargs):
        self.calls.append(kwargs)
        return type("Sequence", (), {"completed": True, "stopped_at": None})()


class ReplanningSequence:
    def __init__(self):
        self.calls = []

    def execute_confirmed_plan(self, **kwargs):
        self.calls.append(kwargs)
        step = kwargs["plan"].steps[0]
        item = SimpleNamespace(
            completed=True,
            reason="",
            verification=ExecutionVerification(
                passed=True,
                actual_quantity=1,
                expected_quantity=1,
                reasons=(),
            ),
        )
        return SimpleNamespace(steps=(item,))


def plan(uid="new", action="BUY"):
    step = type("Step", (), {
        "sequence": 1, "action": action, "instrument_uid": uid,
        "target_value": Decimal("10000"), "depends_on": None,
    })()
    return type("Plan", (), {"steps": (step,)})()


def budget():
    return BudgetPlan(
        account_capital=Decimal("100000"), cash=Decimal("50000"), blocked_cash=Decimal("0"),
        invested=Decimal("50000"), reserve=Decimal("0"), planning_budget=Decimal("100000"),
        investable_cash=Decimal("50000"), slots=5, target_position_value=Decimal("20000"),
    )


def state():
    return AccountState(
        portfolio=None,
        positions=[{"instrument_uid": "old", "quantity": 10}],
        balance=None,
        orders=[],
    )


def test_analysis_mode_never_executes():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)
    controller.enable()

    result = controller.execute(account_id="ACC", plan=plan(), result_factory=lambda step: step, mode=ExecutionMode.ANALYSIS_ONLY)

    assert result.executed is False
    assert result.reason == "AUTONOMOUS_MODE_REQUIRED"
    assert sequence.calls == []


def test_autonomous_mode_requires_explicit_enable():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)

    result = controller.execute(account_id="ACC", plan=plan(), result_factory=lambda step: step, mode=ExecutionMode.AUTONOMOUS)

    assert result.executed is False
    assert result.reason == "AUTONOMOUS_TRADING_DISABLED"
    assert sequence.calls == []


def test_enabled_autonomous_mode_requires_fresh_state():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)

    result = controller.execute(account_id="ACC", plan=plan(), result_factory=lambda step: step, mode=ExecutionMode.AUTONOMOUS)

    assert result.executed is False
    assert result.reason == "FRESH_ACCOUNT_STATE_REQUIRED"
    assert sequence.calls == []


def test_enabled_autonomous_mode_delegates_after_successful_preflight():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)
    controller.enable()

    result = controller.execute(
        account_id="ACC", plan=plan(), result_factory=lambda step: step,
        mode=ExecutionMode.AUTONOMOUS, budget=budget(), state=state(),
    )

    assert result.executed is True
    assert result.reason == "COMPLETED"
    assert len(sequence.calls) == 1


def test_enabled_autonomous_mode_stops_on_preflight_rejection():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)
    controller.enable()

    result = controller.execute(
        account_id="ACC", plan=plan(uid="old"), result_factory=lambda step: step,
        mode=ExecutionMode.AUTONOMOUS, budget=budget(), state=state(),
    )

    assert result.executed is False
    assert result.reason == "PREFLIGHT_REJECTED"
    assert "BUY_ALREADY_HELD:1:old" in result.preflight_reasons
    assert sequence.calls == []


def test_enabled_autonomous_mode_runs_step_refresh_verify_and_replan():
    sequence = ReplanningSequence()
    controller = AutonomousTradingController(sequence)
    controller.enable()
    states = iter([state(), state()])
    built = []
    plans = iter([plan("new"), type("EmptyPlan", (), {"steps": ()})()])

    result = controller.execute_replanned(
        account_id="ACC",
        mode=ExecutionMode.AUTONOMOUS,
        refresh_state=lambda: next(states),
        build_plan=lambda current: (built.append(current) or next(plans)),
        budget_for_state=lambda current: budget(),
        result_factory=lambda step: step,
    )

    assert result.executed is True
    assert result.reason == "COMPLETED"
    assert result.replanning is not None
    assert result.replanning.executed_steps == (1,)
    assert len(sequence.calls) == 1
    assert len(built) == 2


def test_replanned_mode_stops_before_submission_when_preflight_fails():
    sequence = ReplanningSequence()
    controller = AutonomousTradingController(sequence)
    controller.enable()

    result = controller.execute_replanned(
        account_id="ACC",
        mode=ExecutionMode.AUTONOMOUS,
        refresh_state=lambda: state(),
        build_plan=lambda current: plan("old"),
        budget_for_state=lambda current: budget(),
        result_factory=lambda step: step,
    )

    assert result.executed is False
    assert result.reason.startswith("EXECUTION_ERROR:PREFLIGHT_REJECTED")
    assert sequence.calls == []
