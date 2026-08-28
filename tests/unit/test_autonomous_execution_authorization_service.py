from edward.domain.execution import ExecutionMode
from edward.services.autonomous_execution_authorization_service import AutonomousExecutionAuthorizationService
from edward.services.autonomous_execution_plan_service import AutonomousExecutionPlan, ExecutionPlanStep
from edward.services.autonomous_run_state_service import AutonomousRunMode, AutonomousRunState


def plan():
    return AutonomousExecutionPlan(steps=(ExecutionPlanStep(sequence=1, action="BUY", ticker="AAA", instrument_uid="uid", target_value=100, reason="test"),))


def test_analysis_mode_is_rejected():
    result = AutonomousExecutionAuthorizationService().authorize(
        state=AutonomousRunState(mode=AutonomousRunMode.ANALYSIS, enabled=False),
        mode=ExecutionMode.ANALYSIS_ONLY,
        plan=plan(),
    )
    assert result.allowed is False
    assert result.reason == "AUTONOMOUS_MODE_REQUIRED"


def test_autonomous_mode_without_enable_is_rejected():
    result = AutonomousExecutionAuthorizationService().authorize(
        state=AutonomousRunState(mode=AutonomousRunMode.AUTONOMOUS, enabled=False),
        mode=ExecutionMode.AUTONOMOUS,
        plan=plan(),
    )
    assert result.allowed is False
    assert result.reason == "AUTONOMOUS_TRADING_DISABLED"


def test_empty_plan_is_rejected():
    result = AutonomousExecutionAuthorizationService().authorize(
        state=AutonomousRunState(mode=AutonomousRunMode.AUTONOMOUS, enabled=True),
        mode=ExecutionMode.AUTONOMOUS,
        plan=AutonomousExecutionPlan(steps=()),
    )
    assert result.allowed is False
    assert result.reason == "EMPTY_EXECUTION_PLAN"


def test_enabled_autonomous_mode_with_plan_is_authorized():
    result = AutonomousExecutionAuthorizationService().authorize(
        state=AutonomousRunState(mode=AutonomousRunMode.AUTONOMOUS, enabled=True),
        mode=ExecutionMode.AUTONOMOUS,
        plan=plan(),
    )
    assert result.allowed is True
    assert result.reason == "AUTHORIZED"
