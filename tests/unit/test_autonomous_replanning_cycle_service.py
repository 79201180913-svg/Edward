from decimal import Decimal
from types import SimpleNamespace

from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_execution_verification_service import ExecutionVerification
from edward.services.autonomous_replanning_cycle_service import AutonomousReplanningCycleService


def make_plan(sequence: int, uid: str):
    step = ExecutionPlanStep(
        sequence=sequence,
        action="SELL" if uid == "old" else "BUY",
        ticker=uid,
        instrument_uid=uid,
        target_value=Decimal("10000"),
        depends_on=None,
    )
    return AutonomousExecutionPlan(steps=(step,))


def passed_verification():
    return ExecutionVerification(passed=True, actual_quantity=0, expected_quantity=1, reasons=())


def failed_verification():
    return ExecutionVerification(passed=False, actual_quantity=1, expected_quantity=1, reasons=("POSITION_NOT_UPDATED",))


def test_discards_old_plan_and_rebuilds_after_verified_step():
    states = iter(["before", "after", "after-2"])
    plans = iter([make_plan(1, "old"), make_plan(1, "new"), AutonomousExecutionPlan(steps=())])
    built_from = []
    executed = []

    def refresh():
        return next(states)

    def build_plan(state):
        built_from.append(state)
        return next(plans)

    def execute(step):
        executed.append(step.instrument_uid)
        return SimpleNamespace(id="exec-1")

    def verify(step, execution, state):
        return passed_verification()

    result = AutonomousReplanningCycleService(refresh_state=refresh, build_plan=build_plan, execute_step=execute, verify_step=verify).run()
    assert result.completed is True
    assert result.executed_steps == (1, 1)
    assert executed == ["old", "new"]
    assert built_from == ["before", "after", "after-2"]


def test_stops_when_verification_fails_and_does_not_replan():
    states = iter(["before", "after"])
    built = []

    def refresh():
        return next(states)

    def build_plan(state):
        built.append(state)
        return make_plan(1, "old")

    def verify(step, execution, state):
        return failed_verification()

    result = AutonomousReplanningCycleService(refresh_state=refresh, build_plan=build_plan, execute_step=lambda step: SimpleNamespace(id="exec-1"), verify_step=verify).run()
    assert result.completed is False
    assert result.iterations == 1
    assert result.executed_steps == ()
    assert result.stopped_reason == "VERIFICATION_FAILED:POSITION_NOT_UPDATED"
    assert built == ["before"]


def test_stops_on_execution_error():
    result = AutonomousReplanningCycleService(refresh_state=lambda: "state", build_plan=lambda state: make_plan(1, "old"), execute_step=lambda step: (_ for _ in ()).throw(RuntimeError("submit failed")), verify_step=lambda step, execution, state: passed_verification()).run()
    assert result.completed is False
    assert result.stopped_reason == "EXECUTION_ERROR:submit failed"


def test_stops_after_max_iterations():
    result = AutonomousReplanningCycleService(refresh_state=lambda: "state", build_plan=lambda state: make_plan(1, "old"), execute_step=lambda step: SimpleNamespace(id="exec"), verify_step=lambda step, execution, state: passed_verification(), max_iterations=2).run()
    assert result.completed is False
    assert result.iterations == 2
    assert result.executed_steps == (1, 1)
    assert result.stopped_reason == "MAX_ITERATIONS_REACHED"


def test_emits_execution_status_events():
    events = []
    plans = iter([make_plan(1, "old"), AutonomousExecutionPlan(steps=())])
    result = AutonomousReplanningCycleService(
        refresh_state=lambda: "state",
        build_plan=lambda state: next(plans),
        execute_step=lambda step: SimpleNamespace(execution_id="exec-1", status="FILLED"),
        verify_step=lambda step, execution, state: passed_verification(),
        execution_event_callback=events.append,
    ).run()
    assert result.completed is True
    assert result.iterations == 2
    assert [event["status"] for event in events] == ["PLAN", "SUBMITTING", "SUBMITTED", "VERIFYING", "EXECUTED"]
    assert events[2]["execution_id"] == "exec-1"
