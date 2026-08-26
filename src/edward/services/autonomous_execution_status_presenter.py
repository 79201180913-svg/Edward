from __future__ import annotations

from dataclasses import dataclass

from edward.services.autonomous_execution_sequence_service import (
    AutonomousExecutionPhase,
    AutonomousExecutionPhaseEvent,
    AutonomousExecutionSequenceResult,
)


@dataclass(frozen=True, slots=True)
class AutonomousExecutionUiStatus:
    phase: AutonomousExecutionPhase
    title: str
    detail: str
    step: int | None = None
    terminal: bool = False


class AutonomousExecutionStatusPresenter:
    """Translate autonomous execution phases into business-facing UI text."""

    _TITLES = {
        AutonomousExecutionPhase.PREPARING: "Подготовка заявки",
        AutonomousExecutionPhase.EXECUTING: "Исполнение заявки",
        AutonomousExecutionPhase.VERIFYING: "Проверка результата",
        AutonomousExecutionPhase.COMPLETED: "Исполнение завершено",
        AutonomousExecutionPhase.STOPPED: "Исполнение остановлено",
    }

    _DEFAULT_DETAILS = {
        AutonomousExecutionPhase.PREPARING: "Проверка и подготовка текущего шага.",
        AutonomousExecutionPhase.EXECUTING: "Заявка передана в контролируемое исполнение.",
        AutonomousExecutionPhase.VERIFYING: "Проверяется фактическое состояние счёта и позиции.",
        AutonomousExecutionPhase.COMPLETED: "Все шаги плана выполнены и подтверждены.",
        AutonomousExecutionPhase.STOPPED: "Следующие шаги не выполняются до устранения причины остановки.",
    }

    def present(
        self,
        result: AutonomousExecutionSequenceResult,
    ) -> AutonomousExecutionUiStatus:
        event = result.events[-1] if result.events else None
        return self._from_event(result.phase, event, terminal=not self._is_active(result.phase))

    def present_event(self, event: AutonomousExecutionPhaseEvent) -> AutonomousExecutionUiStatus:
        return self._from_event(event.phase, event, terminal=not self._is_active(event.phase))

    def _from_event(
        self,
        phase: AutonomousExecutionPhase,
        event: AutonomousExecutionPhaseEvent | None,
        *,
        terminal: bool,
    ) -> AutonomousExecutionUiStatus:
        detail = (event.message if event and event.message else self._DEFAULT_DETAILS[phase])
        return AutonomousExecutionUiStatus(
            phase=phase,
            title=self._TITLES[phase],
            detail=detail,
            step=event.sequence if event else None,
            terminal=terminal,
        )

    @staticmethod
    def _is_active(phase: AutonomousExecutionPhase) -> bool:
        return phase in {
            AutonomousExecutionPhase.PREPARING,
            AutonomousExecutionPhase.EXECUTING,
            AutonomousExecutionPhase.VERIFYING,
        }


__all__ = ["AutonomousExecutionStatusPresenter", "AutonomousExecutionUiStatus"]
