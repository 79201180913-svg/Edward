from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any

from edward.api.candles_client_patch import install as install_candles_client
from edward.config.application_settings import ApplicationSettingsStore
from edward.services.analysis_service import AnalysisService, Candle
from edward.services.quality_gate_diagnostics import quality_gate_reasons
from edward.storage.analysis_repository import AnalysisSnapshotRepository
from edward.storage.sqlite_store import SQLiteStore


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _number(value: Any) -> float:
    if isinstance(value, dict):
        return float(value.get("units", 0)) + float(value.get("nano", 0)) / 1_000_000_000
    try:
        return float(value)
    except Exception:
        return 0.0


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _parse_candles(response: dict[str, Any]) -> list[Candle]:
    raw = response.get("candles", []) if isinstance(response, dict) else []
    result: list[Candle] = []
    for item in raw:
        timestamp = _field(item, "time", _field(item, "timestamp", None))
        if not timestamp:
            continue
        result.append(
            Candle(
                timestamp=_parse_timestamp(timestamp),
                open=_number(_field(item, "open", 0)),
                high=_number(_field(item, "high", 0)),
                low=_number(_field(item, "low", 0)),
                close=_number(_field(item, "close", 0)),
                volume=_number(_field(item, "volume", 0)),
            )
        )
    return result


def install_analysis_ui(app_class: type[Any], client_class: type[Any]) -> None:
    if getattr(app_class, "_analysis_ui_v04_installed", False):
        return
    install_candles_client(client_class)
    original_page = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        original_page(self)
        if not getattr(self, "instrument_detail", None):
            return
        frame = ttk.LabelFrame(self.content, text="Анализ акции — beta", padding=12)
        frame.pack(fill="x", pady=(14, 0))
        ttk.Label(frame, text="Подбор стратегии с историческим тестированием и Walk Forward.").pack(side="left")
        ttk.Button(frame, text="Анализ акции", command=lambda: _open_analysis(self)).pack(side="right")

    app_class._page_instrument = page_instrument
    app_class._analysis_ui_v04_installed = True


def _open_analysis(app: Any) -> None:
    detail = getattr(app, "instrument_detail", None)
    if not detail:
        return
    window = tk.Toplevel(app)
    window.title(f"Анализ акции — {detail.get('ticker', '')}")
    window.geometry("1200x820")
    window.transient(app)

    top = ttk.Frame(window, padding=16)
    top.pack(fill="x")
    ttk.Label(top, text=f"Анализ: {detail.get('ticker', '')}", style="Title.TLabel").pack(side="left")
    profile_var = tk.StringVar(value="medium_term")
    ttk.Label(top, text="Торговый профиль:").pack(side="left", padx=(30, 6))
    ttk.Combobox(top, textvariable=profile_var, state="readonly", values=("long_term", "medium_term", "speculative"), width=16).pack(side="left")

    status_var = tk.StringVar(value="Готов к запуску")
    ttk.Label(window, textvariable=status_var, padding=(16, 0)).pack(anchor="w")
    progress = ttk.Progressbar(window, mode="indeterminate")
    progress.pack(fill="x", padx=16, pady=10)

    table = ttk.Treeview(
        window,
        columns=("strategy", "score", "return", "dd", "sharpe", "stability", "wf", "gate"),
        show="headings",
        height=12,
    )
    headings = (
        ("strategy", "Стратегия", 175),
        ("score", "Score", 75),
        ("return", "Return %", 85),
        ("dd", "Max DD %", 90),
        ("sharpe", "Sharpe", 75),
        ("stability", "Stability %", 95),
        ("wf", "WF окон", 75),
        ("gate", "Quality Gate", 115),
    )
    for key, label, width in headings:
        table.heading(key, text=label)
        table.column(key, width=width, anchor="center")
    table.pack(fill="both", expand=True, padx=16, pady=10)

    detail_frame = ttk.LabelFrame(window, text="Диагностика Quality Gate", padding=10)
    detail_frame.pack(fill="x", padx=16, pady=(0, 10))

    diag_strategy = tk.StringVar(value="Выберите стратегию")
    ttk.Label(detail_frame, textvariable=diag_strategy, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
    diag_text = tk.Text(detail_frame, height=8, wrap="word")
    diag_text.pack(fill="x", pady=(6, 0))
    diag_text.configure(state="disabled")

    result_text = tk.Text(window, height=6, wrap="word")
    result_text.pack(fill="x", padx=16, pady=(0, 16))
    result_text.configure(state="disabled")

    result_by_strategy: dict[str, Any] = {}

    def show_diagnostics(strategy_name: str) -> None:
        item = result_by_strategy.get(strategy_name)
        if item is None:
            return
        profile_params = AnalysisService._profile_params(profile_var.get())
        checks = quality_gate_reasons(item, profile_params)
        diag_strategy.set(f"{strategy_name} — {'PASS' if item.quality_gate else 'FAIL'}")
        diag_text.configure(state="normal")
        diag_text.delete("1.0", "end")
        for ok, message in checks:
            diag_text.insert("end", f"{'✓' if ok else '✗'} {message}\n")
        diag_text.configure(state="disabled")

    def set_result(result: Any) -> None:
        for item in table.get_children():
            table.delete(item)
        result_by_strategy.clear()
        for item in result.strategies:
            result_by_strategy[item.strategy] = item
            table.insert(
                "",
                "end",
                iid=item.strategy,
                values=(
                    item.strategy,
                    f"{item.score:.1f}",
                    f"{item.return_pct:.2f}",
                    f"{item.max_drawdown_pct:.2f}",
                    f"{item.sharpe:.2f}",
                    f"{item.stability:.0f}",
                    item.wf_windows,
                    "PASS" if item.quality_gate else "FAIL",
                ),
            )
        if result.strategies:
            table.selection_set(result.strategies[0].strategy)
            show_diagnostics(result.strategies[0].strategy)

        result_text.configure(state="normal")
        result_text.delete("1.0", "end")
        result_text.insert(
            "1.0",
            f"Режим: {result.market_regime}\n"
            f"Рекомендация: {result.recommendation or 'нет'}\n"
            f"Confidence: {result.confidence}\n"
            f"Score: {result.score:.1f}\n\n"
            f"{result.explanation}",
        )
        result_text.configure(state="disabled")

    def on_select(_event: Any) -> None:
        selected = table.selection()
        if selected:
            show_diagnostics(selected[0])

    table.bind("<<TreeviewSelect>>", on_select)

    def run() -> None:
        try:
            status_var.set("Получение исторических данных…")
            progress.start(12)
            response = app.client.get_candles(str(detail["instrument_uid"]), interval="CANDLE_INTERVAL_DAY", days=2400)
            candles = _parse_candles(response)
            if len(candles) < 150:
                raise RuntimeError(f"Получено недостаточно свечей: {len(candles)}")
            status_var.set(f"Выполнение анализа: {len(candles)} свечей…")
            settings = ApplicationSettingsStore().load()
            store = SQLiteStore(settings.storage_path)
            service = AnalysisService(store)
            result = service.analyze(
                instrument_uid=str(detail["instrument_uid"]),
                ticker=str(detail.get("ticker", "")),
                candles=candles,
                profile=profile_var.get(),
            )
            run_id = service.save(result)
            AnalysisSnapshotRepository(store).save(result, run_id)
            app.after(0, lambda result=result: (progress.stop(), status_var.set("Анализ завершён и сохранён"), set_result(result)))
        except Exception as exc:
            error_text = str(exc)
            app.after(0, lambda error_text=error_text: (progress.stop(), status_var.set("Ошибка анализа"), messagebox.showerror("Анализ акции", error_text, parent=window)))

    ttk.Button(window, text="Запустить анализ", command=lambda: threading.Thread(target=run, daemon=True).start()).pack(pady=(0, 12))
