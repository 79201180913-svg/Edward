from edward.services.autonomous_execution_sequence_service import AutonomousExecutionPhase, AutonomousExecutionPhaseEvent, AutonomousExecutionSequenceResult
from edward.services.autonomous_execution_status_presenter import AutonomousExecutionStatusPresenter


def test_presenter_translates_active_phase_to_business_text():
    event = AutonomousExecutionPhaseEvent(2, AutonomousExecutionPhase.VERIFYING, "Проверка результата")
    status = AutonomousExecutionStatusPresenter().present_event(event)
    assert status.phase is AutonomousExecutionPhase.VERIFYING
    assert status.title == "Проверка результата"
    assert status.detail == "Проверка результата"
    assert status.step == 2
    assert status.terminal is False


def test_presenter_marks_completed_status_terminal():
    event = AutonomousExecutionPhaseEvent(None, AutonomousExecutionPhase.COMPLETED, "План выполнен")
    status = AutonomousExecutionStatusPresenter().present_event(event)
    assert status.title == "Исполнение завершено"
    assert status.detail == "План выполнен"
    assert status.terminal is True


def test_presenter_marks_stopped_status_terminal():
    event = AutonomousExecutionPhaseEvent(1, AutonomousExecutionPhase.STOPPED, "PREFLIGHT_REJECTED")
    status = AutonomousExecutionStatusPresenter().present_event(event)
    assert status.title == "Исполнение остановлено"
    assert status.detail == "PREFLIGHT_REJECTED"
    assert status.terminal is True


def test_presenter_uses_last_event_for_result():
    event = AutonomousExecutionPhaseEvent(1, AutonomousExecutionPhase.COMPLETED, "Шаг выполнен")
    result = AutonomousExecutionSequenceResult(steps=(), completed=True, phase=AutonomousExecutionPhase.COMPLETED, events=(event,))
    status = AutonomousExecutionStatusPresenter().present(result)
    assert status.phase is AutonomousExecutionPhase.COMPLETED
    assert status.detail == "Шаг выполнен"
