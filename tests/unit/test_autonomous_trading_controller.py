from edward.domain.execution import ExecutionMode
from edward.services.autonomous_trading_controller import AutonomousTradingController


class FakeSequence:
    def __init__(self):
        self.calls = []

    def execute_confirmed_plan(self, **kwargs):
        self.calls.append(kwargs)
        return type("Sequence", (), {"completed": True, "stopped_at": None})()


def plan():
    return type("Plan", (), {"steps": (object(),)})()


def test_analysis_mode_never_executes():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)
    controller.enable()

    result = controller.execute(
        account_id="ACC",
        plan=plan(),
        result_factory=lambda step: step,
        mode=ExecutionMode.ANALYSIS_ONLY,
    )

    assert result.executed is False
    assert result.reason == "AUTONOMOUS_MODE_REQUIRED"
    assert sequence.calls == []


def test_autonomous_mode_requires_explicit_enable():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)

    result = controller.execute(
        account_id="ACC",
        plan=plan(),
        result_factory=lambda step: step,
        mode=ExecutionMode.AUTONOMOUS,
    )

    assert result.executed is False
    assert result.reason == "AUTONOMOUS_TRADING_DISABLED"
    assert sequence.calls == []


def test_enabled_autonomous_mode_delegates_to_sequence():
    sequence = FakeSequence()
    controller = AutonomousTradingController(sequence)
    controller.enable()

    result = controller.execute(
        account_id="ACC",
        plan=plan(),
        result_factory=lambda step: step,
        mode=ExecutionMode.AUTONOMOUS,
    )

    assert result.executed is True
    assert result.reason == "COMPLETED"
    assert len(sequence.calls) == 1
