from __future__ import annotations

from tkinter import messagebox
from typing import Any, Callable


def can_enqueue_opportunity(result: Any) -> bool:
    decision = str(getattr(result, "decision", "") or "").upper()
    return (
        bool(getattr(result, "execution_ready", False))
        and decision in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}
        and int(getattr(result, "recommended_quantity", 0) or 0) > 0
    )


def enqueue_opportunity_result(*, bridge: Any, account_id: str, result: Any) -> Any:
    if not can_enqueue_opportunity(result):
        raise ValueError("Инструмент не готов к исполнению и не может быть передан в очередь")
    return bridge.enqueue_opportunity(account_id=account_id, result=result)


def enqueue_button_text(result: Any | None) -> str:
    return "Передать в исполнение" if result is not None and can_enqueue_opportunity(result) else "Исполнение недоступно"


def show_enqueue_result(result: Any) -> None:
    if getattr(result, "accepted", False):
        messagebox.showinfo("Центр исполнения", "Решение передано в очередь исполнения. Заявка не отправлена.")
    else:
        messagebox.showwarning(
            "Центр исполнения",
            getattr(result, "reason", "Решение заблокировано и не добавлено в очередь."),
        )


class ExecutionQueueActionController:
    def __init__(self, *, bridge: Any, account_id_provider: Callable[[], str | None]) -> None:
        self.bridge = bridge
        self.account_id_provider = account_id_provider

    def enqueue(self, result: Any) -> Any:
        account_id = self.account_id_provider()
        if not account_id:
            raise RuntimeError("Не найден активный торговый счёт")
        return enqueue_opportunity_result(bridge=self.bridge, account_id=account_id, result=result)

    def status_text(self, result: Any) -> str:
        return "Готово к передаче в исполнение" if can_enqueue_opportunity(result) else "Исполнение недоступно"


__all__ = [
    "ExecutionQueueActionController",
    "can_enqueue_opportunity",
    "enqueue_opportunity_result",
    "enqueue_button_text",
    "show_enqueue_result",
]
