from __future__ import annotations

from typing import Any

from edward.domain.execution import ExecutionStatus


def can_enqueue_execution(result: Any, status: ExecutionStatus | None = None) -> bool:
    decision = str(getattr(result, "decision", "") or "").upper()
    ready = bool(getattr(result, "execution_ready", False))
    if status is not None:
        ready = ready and status is ExecutionStatus.READY
    return (
        ready
        and decision in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}
        and int(getattr(result, "recommended_quantity", getattr(result, "quantity", 0)) or 0) > 0
    )


def enqueue_button_label(value: Any | None) -> str:
    if isinstance(value, bool):
        return "Передать в исполнение" if value else "Исполнение недоступно"
    return "Передать в исполнение" if value is not None and can_enqueue_execution(value) else "Исполнение недоступно"


def enqueue_execution(*, bridge: Any, account_id: str, result: Any, status: ExecutionStatus | None = None) -> Any:
    if not can_enqueue_execution(result, status):
        raise ValueError("Инструмент не готов к исполнению и не может быть передан в очередь")
    return bridge.enqueue_opportunity(account_id=account_id, result=result)


__all__ = ["can_enqueue_execution", "enqueue_button_label", "enqueue_execution"]
