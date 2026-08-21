from __future__ import annotations

from typing import Any
from tkinter import ttk

from edward.api.tinvest_adapter_client import TInvestAdapterClient

_SENTINEL = "__edward_compat_fixes_installed__"


def _page_history(app: Any) -> None:
    ttk.Label(app.content, text="История операций", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
    tree = app._tree(
        app.content,
        ("Дата", "Время", "Счёт", "Заявка", "Тикер", "Операция", "Количество", "Цена", "Сумма", "Комиссия", "Валюта", "Статус"),
        (90, 80, 300, 300, 100, 100, 100, 110, 120, 110, 80, 100),
    )
    rows = app.history.read_all()
    for row in rows:
        tree.insert("", "end", values=tuple(row.get(k, "") for k in ("date", "time", "account_id", "order_id", "ticker", "operation", "quantity", "execution_price", "amount", "commission", "currency", "status")))
    print(f"[HISTORY] Загружено записей: {len(rows)}", flush=True)


def install_compat_fixes(EdwardApp: Any) -> None:
    if getattr(EdwardApp, _SENTINEL, False):
        return

    original_get_instrument = TInvestAdapterClient.get_instrument
    def normalized_get_instrument(self: TInvestAdapterClient, instrument_id: str) -> dict:
        result = original_get_instrument(self, instrument_id)
        if isinstance(result, dict) and isinstance(result.get("instrument"), dict):
            merged = dict(result["instrument"])
            merged.setdefault("instrument", result["instrument"])
            return merged
        return result
    TInvestAdapterClient.get_instrument = normalized_get_instrument

    EdwardApp._page_history = _page_history
    setattr(EdwardApp, _SENTINEL, True)
