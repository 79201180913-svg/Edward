from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable, Optional, Protocol

from edward.domain.execution import (
    ExecutionEvent,
    ExecutionEventType,
    ExecutionJournal,
    ExecutionJournalEntry,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)


class ExecutionAdapter(Protocol):
    def submit(self, request: ExecutionRequest) -> str: ...
    def cancel(self, broker_order_id: str) -> None: ...
    def get_status(self, broker_order_id: str) -> ExecutionResult: ...


class InMemoryExecutionJournal:
    def __init__(self) -> None:
        self._entries: dict[str, ExecutionJournalEntry] = {}

    def append(self, entry: ExecutionJournalEntry) -> None:
        if entry.execution_id in self._entries:
            raise ValueError("execution_id already exists")
        self._entries[entry.execution_id] = entry

    def update(self, entry: ExecutionJournalEntry) -> None:
        if entry.execution_id not in self._entries:
            raise KeyError(entry.execution_id)
        self._entries[entry.execution_id] = entry

    def get(self, execution_id: str) -> Optional[ExecutionJournalEntry]:
        return self._entries.get(execution_id)


EventCallback = Callable[[ExecutionEvent], None]


class ExecutionEngine:
    """Stateful execution coordinator for user-confirmed and explicitly authorized autonomous decisions."""

    def __init__(self, *, journal: ExecutionJournal | None = None, adapter: ExecutionAdapter | None = None, event_callback: EventCallback | None = None) -> None:
        self.journal = journal or InMemoryExecutionJournal()
        self.adapter = adapter
        self.event_callback = event_callback

    def create(self, request: ExecutionRequest) -> ExecutionResult:
        if self.journal.get(request.execution_id) is not None:
            raise ValueError("execution_id already exists")
        self.journal.append(self._entry(request, ExecutionStatus.CREATED))
        self._emit(request.execution_id, ExecutionEventType.CREATED, ExecutionStatus.CREATED, "Исполнение создано")
        return ExecutionResult(request.execution_id, ExecutionStatus.CREATED)

    def validate(self, request: ExecutionRequest) -> ExecutionResult:
        self._require_existing(request.execution_id)
        self._update_status(request.execution_id, ExecutionStatus.VALIDATING)
        self._emit(request.execution_id, ExecutionEventType.VALIDATION_STARTED, ExecutionStatus.VALIDATING, "Начата проверка исполнения")
        errors: list[str] = []
        if not request.execution_ready:
            errors.append("EXECUTION_NOT_READY")
        if request.quantity <= 0:
            errors.append("INVALID_QUANTITY")
        if request.order_type.lower() == "limit" and request.entry_price is None:
            errors.append("ENTRY_PRICE_REQUIRED")
        if request.stop_price is not None and request.stop_price <= 0:
            errors.append("INVALID_STOP_PRICE")
        if errors:
            self._update_status(request.execution_id, ExecutionStatus.BLOCKED, error_code=errors[0], error_message=";".join(errors))
            self._emit(request.execution_id, ExecutionEventType.VALIDATION_FAILED, ExecutionStatus.BLOCKED, "Исполнение заблокировано", {"reasons": errors})
            return ExecutionResult(request.execution_id, ExecutionStatus.BLOCKED, error_code=errors[0], error_message=";".join(errors))
        self._update_status(request.execution_id, ExecutionStatus.READY)
        self._emit(request.execution_id, ExecutionEventType.VALIDATION_PASSED, ExecutionStatus.READY, "Проверка исполнения пройдена")
        return ExecutionResult(request.execution_id, ExecutionStatus.READY)

    def plan(self, request: ExecutionRequest) -> ExecutionRequest:
        current = self._require_existing(request.execution_id)
        if current.status not in {ExecutionStatus.READY, ExecutionStatus.WAITING_CONFIRMATION}:
            raise ValueError(f"execution is not ready for planning: {current.status}")
        return request

    def require_confirmation(self, request: ExecutionRequest) -> ExecutionResult:
        current = self._require_existing(request.execution_id)
        if current.status != ExecutionStatus.READY:
            raise ValueError(f"confirmation is not available from {current.status}")
        self._update_status(request.execution_id, ExecutionStatus.WAITING_CONFIRMATION)
        self._emit(request.execution_id, ExecutionEventType.CONFIRMATION_REQUIRED, ExecutionStatus.WAITING_CONFIRMATION, "Требуется подтверждение пользователя")
        return ExecutionResult(request.execution_id, ExecutionStatus.WAITING_CONFIRMATION)

    def confirm(self, request: ExecutionRequest) -> ExecutionResult:
        current = self._require_existing(request.execution_id)
        if current.status != ExecutionStatus.WAITING_CONFIRMATION:
            raise ValueError(f"confirmation is not expected from {current.status}")
        self._emit(request.execution_id, ExecutionEventType.CONFIRMED, ExecutionStatus.WAITING_CONFIRMATION, "Пользователь подтвердил исполнение")
        return ExecutionResult(request.execution_id, ExecutionStatus.WAITING_CONFIRMATION)

    def submit(self, request: ExecutionRequest, *, mode: ExecutionMode = ExecutionMode.USER_CONFIRMATION) -> ExecutionResult:
        current = self._require_existing(request.execution_id)
        if self.adapter is None:
            raise RuntimeError("execution adapter is not configured")
        if mode is ExecutionMode.USER_CONFIRMATION:
            if current.status != ExecutionStatus.WAITING_CONFIRMATION:
                raise ValueError(f"submission is not allowed from {current.status}")
        elif mode is ExecutionMode.AUTONOMOUS:
            if current.status != ExecutionStatus.READY:
                raise ValueError(f"autonomous submission is not allowed from {current.status}")
        else:
            raise ValueError(f"unsupported execution mode: {mode}")

        self._update_status(request.execution_id, ExecutionStatus.SUBMITTING)
        self._emit(request.execution_id, ExecutionEventType.SUBMITTING, ExecutionStatus.SUBMITTING, "Автономная отправка заявки" if mode is ExecutionMode.AUTONOMOUS else "Отправка заявки")
        logger.info("[EXECUTION] ORDER CREATE execution_id=%s ticker=%s side=%s quantity=%s order_type=%s mode=%s", request.execution_id, request.ticker, request.side, request.quantity, request.order_type, mode.value)
        try:
            broker_order_id = self.adapter.submit(request)
        except Exception as exc:
            logger.exception("[EXECUTION] ORDER CREATE FAILED execution_id=%s", request.execution_id)
            self._update_status(request.execution_id, ExecutionStatus.FAILED, error_code=type(exc).__name__, error_message=str(exc))
            self._emit(request.execution_id, ExecutionEventType.ERROR, ExecutionStatus.FAILED, "Ошибка отправки заявки", {"error": str(exc)})
            return ExecutionResult(request.execution_id, ExecutionStatus.FAILED, error_code=type(exc).__name__, error_message=str(exc))

        logger.info("[EXECUTION] ORDER CREATE SUCCESS execution_id=%s broker_order_id=%s", request.execution_id, broker_order_id)
        self._update_status(request.execution_id, ExecutionStatus.SUBMITTED, broker_order_id=broker_order_id)
        self._emit(request.execution_id, ExecutionEventType.SUBMITTED, ExecutionStatus.SUBMITTED, "Заявка отправлена", {"broker_order_id": broker_order_id})
        return ExecutionResult(request.execution_id, ExecutionStatus.SUBMITTED, broker_order_id=broker_order_id)

    def monitor(self, execution_id: str) -> ExecutionResult:
        entry = self._require_existing(execution_id)
        if entry.broker_order_id is None:
            return ExecutionResult(execution_id, entry.status, error_code=entry.error_code, error_message=entry.error_message)
        if self.adapter is None:
            raise RuntimeError("execution adapter is not configured")
        current = self.adapter.get_status(entry.broker_order_id)
        if current.status != entry.status:
            self._update_status(execution_id, current.status, broker_order_id=entry.broker_order_id, error_code=current.error_code, error_message=current.error_message)
        return current

    def cancel(self, execution_id: str) -> ExecutionResult:
        entry = self._require_existing(execution_id)
        if entry.broker_order_id is not None and self.adapter is not None:
            self.adapter.cancel(entry.broker_order_id)
        self._update_status(execution_id, ExecutionStatus.CANCELLED)
        return ExecutionResult(execution_id, ExecutionStatus.CANCELLED)

    def _require_existing(self, execution_id: str) -> ExecutionJournalEntry:
        entry = self.journal.get(execution_id)
        if entry is None:
            raise KeyError(execution_id)
        return entry

    def _entry(self, request: ExecutionRequest, status: ExecutionStatus) -> ExecutionJournalEntry:
        return ExecutionJournalEntry(
            execution_id=request.execution_id,
            account_id=request.account_id,
            ticker=request.ticker,
            instrument_uid=request.instrument_uid,
            decision=request.decision,
            quantity=request.quantity,
            status=status,
            broker_order_id=None,
            error_code=None,
            error_message=None,
        )

    def _update_status(self, execution_id: str, status: ExecutionStatus, *, broker_order_id: str | None = None, error_code: str | None = None, error_message: str | None = None) -> None:
        current = self._require_existing(execution_id)
        self.journal.update(replace(current, status=status, broker_order_id=broker_order_id if broker_order_id is not None else current.broker_order_id, error_code=error_code, error_message=error_message))

    def _emit(self, execution_id: str, event_type: ExecutionEventType, status: ExecutionStatus, message: str, details: dict | None = None) -> None:
        if self.event_callback is None:
            return
        self.event_callback(ExecutionEvent(execution_id=execution_id, event_type=event_type, status=status, message=message, details=details or {}))


__all__ = ["ExecutionAdapter", "ExecutionEngine", "InMemoryExecutionJournal"]
