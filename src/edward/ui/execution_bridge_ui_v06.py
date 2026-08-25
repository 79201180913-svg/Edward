from __future__ import annotations

from typing import Any


def can_enqueue_execution(result: Any) -> bool:
    decision = str(getattr(result, "decision", "") or "").upper()
    return (
        bool(getattr(result, "execution_ready", False))
        and decision in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}
        and int(getattr(result, "recommended_quantity", 0) or 0) > 0
    )


def enqueue_button_label(result: Any | None) -> str:
    return "Передать в исполнение" if result is not None and can_enqueue_execution(result) else "Исполнение недоступно"


def enqueue_execution(*, bridge: Any, account_id: str, result: Any) -> Any:
    if not can_enqueue_execution(result):
        raise ValueError("Инструмент не готов к исполнению и не может быть передан в очередь")
    return bridge.enqueue_opportunity(account_id=account_id, result=result)


__all__ = ["can_enqueue_execution", "enqueue_button_label", "enqueue_execution"]
