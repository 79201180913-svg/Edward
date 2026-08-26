from edward.domain.execution import ExecutionMode


def test_v07_has_explicit_autonomous_execution_mode():
    assert ExecutionMode.AUTONOMOUS.value == "autonomous"
    assert ExecutionMode.ANALYSIS_ONLY.value != ExecutionMode.AUTONOMOUS.value
