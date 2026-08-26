from edward.services.autonomous_run_state_service import AutonomousRunMode, AutonomousRunStateService


def test_control_state_starts_in_analysis_mode():
    service = AutonomousRunStateService()
    assert service.snapshot().mode is AutonomousRunMode.ANALYSIS
    assert service.snapshot().enabled is False


def test_autonomous_mode_requires_explicit_enable():
    service = AutonomousRunStateService()
    service.set_mode(AutonomousRunMode.AUTONOMOUS)
    assert service.snapshot().enabled is False
    service.set_enabled(True)
    assert service.snapshot().enabled is True


def test_switching_to_analysis_turns_execution_off():
    service = AutonomousRunStateService()
    service.set_mode(AutonomousRunMode.AUTONOMOUS)
    service.set_enabled(True)
    service.set_mode(AutonomousRunMode.ANALYSIS)
    assert service.snapshot().enabled is False
