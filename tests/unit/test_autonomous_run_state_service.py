import pytest

from edward.services.autonomous_run_state_service import (
    AutonomousRunMode,
    AutonomousRunStateService,
)


def test_defaults_to_analysis_and_disabled():
    state = AutonomousRunStateService().snapshot()
    assert state.mode is AutonomousRunMode.ANALYSIS
    assert state.enabled is False
    assert state.status == "READY"


def test_autonomous_mode_can_be_enabled():
    service = AutonomousRunStateService()
    service.set_mode(AutonomousRunMode.AUTONOMOUS)
    state = service.set_enabled(True)
    assert state.mode is AutonomousRunMode.AUTONOMOUS
    assert state.enabled is True


def test_cannot_enable_autonomous_execution_in_analysis_mode():
    service = AutonomousRunStateService()
    with pytest.raises(ValueError, match="AUTONOMOUS_MODE_REQUIRED"):
        service.set_enabled(True)


def test_switching_back_to_analysis_disables_execution():
    service = AutonomousRunStateService()
    service.set_mode(AutonomousRunMode.AUTONOMOUS)
    service.set_enabled(True)
    state = service.set_mode(AutonomousRunMode.ANALYSIS)
    assert state.mode is AutonomousRunMode.ANALYSIS
    assert state.enabled is False


def test_runtime_status_preserves_control_state():
    service = AutonomousRunStateService()
    service.set_mode(AutonomousRunMode.AUTONOMOUS)
    service.set_enabled(True)
    state = service.update(status="EXECUTING", message="step 1", execution_id="exec-1")
    assert state.enabled is True
    assert state.mode is AutonomousRunMode.AUTONOMOUS
    assert state.status == "EXECUTING"
    assert state.execution_id == "exec-1"
