from __future__ import annotations

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


class ExecutionAdapter(Protocol):
    """Broker adapter boundary implemented by 0.6.3."""

    def submit(self, request: ExecutionRequest) -> str:
        ...

    def cancel(self, broker_order_id: str) -> None:
        ...

    def get_status(self, broker_order_id: str) -> ExecutionResult:
        ...


class InMemoryExecutionJournal:
    """Deterministic journal implementation for 0.6.2 tests and local service use."""

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
    """Stateful execution coordinator for already-approved trading decisions."""

    def __init__(
        self,
        *,
        journal: ExecutionJournal | None = None,
        adapter: ExecutionAdapter | None = None,
        event_callback: EventCallback | None = None,
    ) -> None:
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
            self._update_status(
                request.execution_id,
                ExecutionStatus.BLOCKED,
                error_code=errors[0],
                error_message=";".join(errors),
            )
            self._emit(
                request.execution_id,
                ExecutionEventType.VALIDATION_FAILED,
                ExecutionStatus.BLOCKED,
                "Исполнение заблокировано",
                {"reasons": errors},
            )
            return ExecutionResult(
                request.execution_id,
                ExecutionStatus.BLOCKED,
                error_code=errors[0],
                error_message=";".join(errors),
            )

        self._update_status(request.execution_id, ExecutionStatus.READY)
        self._emit(
            request.execution_id,
            ExecutionEventType.VALIDATION_PASSED,
            ExecutionStatus.READY,
            "Проверка исполнения пройдена",
        )
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
        self._emit(
            request.execution_id,
            ExecutionEventType.CONFIRMATION_REQUIRED,
            ExecutionStatus.WAITING_CONFIRMATION,
            "Требуется подтверждение пользователя",
        )
        return ExecutionResult(request.execution_id, ExecutionStatus.WAITING_CONFIRMATION)

    def confirm(self, request: ExecutionRequest) -> ExecutionResult:
        current = self._require_existing(request.execution_id)
        if current.status != ExecutionStatus.WAITING_CONFIRMATION:
            raise ValueError(f"confirmation is not expected from {current.status}")
        self._emit(
            request.execution_id,
            ExecutionEventType.CONFIRMED,
            ExecutionStatus.WAITING_CONFIRMATION,
            "Пользователь подтвердил исполнение",
        )
        return ExecutionResult(request.execution_id, ExecutionStatus.WAITING_CONFIRMATION)

    def submit(
        self,
        request: ExecutionRequest,
        *,
        mode: ExecutionMode = ExecutionMode.USER_CONFIRMATION,
    ) -> ExecutionResult:
        current = self._require_existing(request.execution_id)
        if mode != ExecutionMode.USER_CONFIRMATION:
            raise ValueError("v0.6.2 supports controlled user-confirmation execution only")
        if current.status != ExecutionStatus.WAITING_CONFIRMATION:
            raise ValueError(f"submission is not allowed from {current.status}")
        if self.adapter is None:
            raise RuntimeError("execution adapter is not configured")

        self._update_status(request.execution_id, ExecutionStatus.SUBMITTING)
        self._emit(
            request.execution_id,
            ExecutionEventType.SUBMITTING,
            ExecutionStatus.SUBMITTING,
            "Отправка заявки",
        )
        try:
            broker_order_id = self.adapter.submit(request)
        except Exception as exc:
            self._update_status(
                request.execution_id,
                ExecutionStatus.FAILED,
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            self._emit(
                request.execution_id,
                ExecutionEventType.ERROR,
                ExecutionStatus.FAILED,
                "Ошибка отправки заявки",
                {"error": str(exc)},
            )
            return ExecutionResult(
                request.execution_id,
                ExecutionStatus.FAILED,
                error_code=type(exc).__name__,
                error_message=str(exc),
            )

        self._update_status(
            request.execution_id,
            ExecutionStatus.SUBMITTED,
            broker_order_id=broker_order_id,
        )
        self._emit(
            request.execution_id,
            ExecutionEventType.SUBMITTED,
            ExecutionStatus.SUBMITTED,
            "Заявка отправлена",
            {"broker_order_id": broker_order_id},
        )
        return ExecutionResult(
            request.execution_id,
            ExecutionStatus.SUBMITTED,
            broker_order_id=broker_order_id,
        )

    def monitor(self, execution_id: str) -> ExecutionResult:
        entry = self._require_existing(execution_id)
        if not entry.broker_order_id:
            raise ValueError("broker order id is not available")
        if self.adapter is None:
            raise RuntimeError("execution adapter is not configured")

        result = self.adapter.get_status(entry.broker_order_id)
        self._update_from_result(execution_id, result)
        self._emit(
            execution_id,
            ExecutionEventType.STATUS_CHANGED,
            result.status,
            "Получен статус заявки",
        )
        if result.filled_quantity > 0:
            self._emit(
                execution_id,
                ExecutionEventType.FILL_UPDATED,
                result.status,
                "Обновлено исполнение",
                {"filled_quantity": str(result.filled_quantity)},
            )
        return result

    def cancel(self, execution_id: str) -> ExecutionResult:
        entry = self._require_existing(execution_id)
        if not entry.broker_order_id:
            raise ValueError("broker order id is not available")
        if self.adapter is None:
            raise RuntimeError("execution adapter is not configured")
        if entry.status not in {ExecutionStatus.SUBMITTED, ExecutionStatus.PARTIALLY_FILLED}:
            raise ValueError(f"cancellation is not available from {entry.status}")

        self._emit(
            execution_id,
            ExecutionEventType.CANCEL_REQUESTED,
            entry.status,
            "Запрошена отмена заявки",
        )
        self.adapter.cancel(entry.broker_order_id)
        self._update_status(execution_id, ExecutionStatus.CANCELLED)
        self._emit(
            execution_id,
            ExecutionEventType.CANCELLED,
            ExecutionStatus.CANCELLED,
            "Заявка отменена",
        )
        return ExecutionResult(
            execution_id,
            ExecutionStatus.CANCELLED,
            broker_order_id=entry.broker_order_id,
        )

    def recover(self, execution_id: str) -> ExecutionResult:
        entry = self._require_existing(execution_id)
        if entry.status in {ExecutionStatus.SUBMITTED, ExecutionStatus.PARTIALLY_FILLED}:
            return self.monitor(execution_id)
        return ExecutionResult(
            execution_id,
            entry.status,
            broker_order_id=entry.broker_order_id,
            filled_quantity=entry.filled_quantity,
            average_fill_price=entry.average_fill_price,
            commission=entry.commission,
            error_code=entry.error_code,
            error_message=entry.error_message,
        )

    def _entry(self, request: ExecutionRequest, status: ExecutionStatus) -> ExecutionJournalEntry:
        return ExecutionJournalEntry(
            execution_id=request.execution_id,
            account_id=request.account_id,
            instrument_uid=request.instrument_uid,
            decision=request.decision,
            side=request.side,
            order_type=request.order_type,
            requested_quantity=request.quantity,
            requested_price=request.entry_price,
            stop_price=request.stop_price,
            execution_ready=request.execution_ready,
            status=status,
        )

    def _require_existing(self, execution_id: str) -> ExecutionJournalEntry:
        entry = self.journal.get(execution_id)
        if entry is None:
            raise KeyError(execution_id)
        return entry

    def _update_status(self, execution_id: str, status: ExecutionStatus, **changes: object) -> ExecutionJournalEntry:
        current = self._require_existing(execution_id)
        updated = replace(current, status=status, **changes)
        self.journal.update(updated)
        return updated

    def _update_from_result(self, execution_id: str, result: ExecutionResult) -> ExecutionJournalEntry:
        current = self._require_existing(execution_id)
        updated = replace(
            current,
            status=result.status,
            broker_order_id=result.broker_order_id or current.broker_order_id,
            filled_quantity=result.filled_quantity,
            average_fill_price=result.average_fill_price,
            commission=result.commission,
            error_code=result.error_code,
            error_message=result.error_message,
        )
        self.journal.update(updated)
        return updated

    def _emit(
        self,
        execution_id: str,
        event_type: ExecutionEventType,
        status: ExecutionStatus,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.event_callback is None:
            return
        self.event_callback(
            ExecutionEvent(
                execution_id=execution_id,
                event_type=event_type,
                status=status,
                message=message,
                payload=payload or {},
            )
        )
