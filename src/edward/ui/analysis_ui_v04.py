from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any

from edward.api.candles_client_patch import install as install_candles_client
from edward.config.application_settings import ApplicationSettingsStore
from edward.services.analysis_service import AnalysisService, Candle
from edward.services.decision_engine import (
    DecisionEngine,
    DecisionRequest,
    OpportunityContext,
    PositionContextData,
    Scenario,
)
from edward.services.opportunity_engine import OpportunityEngine
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


def _position_context(app: Any, instrument_uid: str) -> PositionContextData:
    account_id = getattr(app.context, "active_account_id", None)
    if not account_id:
        return PositionContextData()
    try:
        positions = app.client.get_positions(account_id)
        collection = positions if isinstance(positions, list) else _field(positions, "securities", []) or []
        for position in collection:
            if str(_field(position, "instrument_uid", "")) != instrument_uid:
                continue
            return PositionContextData(
                quantity=_number(_field(position, "balance", 0)),
                average_price=_number(_field(position, "average_position_price", _field(position, "average_price", 0))) or None,
                current_price=_number(_field(position, "current_price", 0)) or None,
                pnl=_number(_field(position, "expected_yield", _field(position, "expected_yield_fifo", 0))),
                portfolio_weight_pct=0.0,
                target_weight_pct=0.0,
            )
    except Exception:
        return PositionContextData()
    return PositionContextData()


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
        ttk.Label(frame, text="Подбор стратегии с историческим тестированием, Opportunity Analysis и Decision Engine.").pack(side="left")
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
    window.minsize(1050, 700)
    window.transient(app)

    top = ttk.Frame(window, padding=16)
    top.pack(fill="x")
    ttk.Label(top, text=f"Анализ: {detail.get('ticker', '')}", style="Title.TLabel").pack(side="left")
    profile_var = tk.StringVar(value="medium_term")
    ttk.Label(top, text="Торговый профиль:").pack(side="left", padx=(30, 6))
    ttk.Combobox(top, textvariable=profile_var, state="readonly", values=("long_term", "medium_term", "speculative"), width=16).pack(side="left")
    status_var = tk.StringVar(value="Готов к запуску")
    ttk.Label(top, textvariable=status_var).pack(side="left", padx=(28, 0))
    progress = ttk.Progressbar(top, mode="indeterminate", length=180)
    progress.pack(side="left", padx=(12, 0))
    start_button = ttk.Button(top, text="Запустить анализ")
    start_button.pack(side="right")

    table = ttk.Treeview(window, columns=("strategy", "score", "return", "dd", "sharpe", "stability", "wf", "gate"), show="headings", height=12)
    headings = (("strategy", "Стратегия", 175), ("score", "Score", 75), ("return", "Return %", 85), ("dd", "Max DD %", 90), ("sharpe", "Sharpe", 75), ("stability", "Stability %", 95), ("wf", "WF окон", 75), ("gate", "Quality Gate", 115))
    for key, label, width in headings:
        table.heading(key, text=label)
        table.column(key, width=width, anchor="center")
    table.pack(fill="both", expand=True, padx=16, pady=10)

    detail_frame = ttk.LabelFrame(window, text="Диагностика Quality Gate", padding=10)
    detail_frame.pack(fill="x", padx=16, pady=(0, 10))
    diag_strategy = tk.StringVar(value="Выберите стратегию")
    ttk.Label(detail_frame, textvariable=diag_strategy, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
    diag_text = tk.Text(detail_frame, height=6, wrap="word")
    diag_text.pack(fill="x", pady=(6, 0))
    diag_text.configure(state="disabled")

    decision_frame = ttk.LabelFrame(window, text="Торговое решение", padding=10)
    decision_frame.pack(fill="x", padx=16, pady=(0, 10))
    decision_var = tk.StringVar(value="Решение: —")
    decision_scores = tk.StringVar(value="Strategy Score: —    Opportunity Score: —    Позиция: —")
    decision_reason = tk.StringVar(value="")
    ttk.Label(decision_frame, textvariable=decision_var, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(decision_frame, textvariable=decision_scores).pack(anchor="w", pady=(4, 0))
    ttk.Label(decision_frame, textvariable=decision_reason, wraplength=1100, justify="left").pack(anchor="w", pady=(4, 0))

    result_text = tk.Text(window, height=5, wrap="word")
    result_text.pack(fill="x", padx=16, pady=(0, 16))
    result_text.configure(state="disabled")

    result_by_strategy: dict[str, Any] = {}
    state: dict[str, Any] = {"result": None, "candles": [], "position": PositionContextData()}

    def set_running(running: bool) -> None:
        start_button.configure(state="disabled" if running else "normal")
        if running:
            progress.start(12)
        else:
            progress.stop()

    def show_diagnostics(strategy_name: str) -> None:
        item = result_by_strategy.get(strategy_name)
        if item is None:
            diag_strategy.set("Выберите стратегию")
            diag_text.configure(state="normal")
            diag_text.delete("1.0", "end")
            diag_text.configure(state="disabled")
            return
        checks = quality_gate_reasons(item, AnalysisService._profile_params(profile_var.get()))
        diag_strategy.set(f"{strategy_name} — {'PASS' if item.quality_gate else 'FAIL'}")
        diag_text.configure(state="normal")
        diag_text.delete("1.0", "end")
        for ok, message in checks:
            diag_text.insert("end", f"{'✓' if ok else '✗'} {message}\n")
        diag_text.configure(state="disabled")

    def apply_decision(strategy_result: Any | None) -> None:
        result = state.get("result")
        candles = state.get("candles") or []
        if result is None or not candles:
            return
        opportunity = OpportunityEngine.evaluate(result, candles, strategy_result)
        position = state.get("position") or PositionContextData()
        decision = DecisionEngine.evaluate(
            DecisionRequest(
                scenario=Scenario.SINGLE_INSTRUMENT,
                position=position,
                opportunity=opportunity.context,
                strategy_score=strategy_result.score if strategy_result else 0.0,
                strategy_name=strategy_result.strategy if strategy_result else None,
                strategy_quality=bool(strategy_result and strategy_result.quality_gate),
                portfolio_allows_add=False,
                exit_signal=False,
                profile=profile_var.get(),
            )
        )
        decision_var.set(f"Решение: {decision.decision.value}")
        decision_scores.set(
            f"Strategy Score: {decision.strategy_score:.1f}    "
            f"Opportunity Score: {decision.opportunity_score:.1f}    "
            f"Позиция: {'есть' if position.is_open else 'нет'}"
        )
        decision_reason.set(decision.explanation)

    def set_result(result: Any, candles: list[Candle], position: PositionContextData) -> None:
        for item in table.get_children():
            table.delete(item)
        result_by_strategy.clear()
        state["result"] = result
        state["candles"] = candles
        state["position"] = position
        for item in result.strategies:
            result_by_strategy[item.strategy] = item
            table.insert("", "end", iid=item.strategy, values=(item.strategy, f"{item.score:.1f}", f"{item.return_pct:.2f}", f"{item.max_drawdown_pct:.2f}", f"{item.sharpe:.2f}", f"{item.stability:.0f}", item.wf_windows, "PASS" if item.quality_gate else "FAIL"))
        if result.strategies:
            table.selection_set(result.strategies[0].strategy)
            show_diagnostics(result.strategies[0].strategy)
        winner = next((item for item in result.strategies if item.quality_gate), None)
        apply_decision(winner)
        result_text.configure(state="normal")
        result_text.delete("1.0", "end")
        result_text.insert("1.0", f"Режим: {result.market_regime}\nСтратегия: {result.recommendation or 'нет прошедшей стратегии'}\nConfidence: {result.confidence}\nStrategy Score: {result.score:.1f}\n\n{result.explanation}")
        result_text.configure(state="disabled")

    def on_select(_event: Any) -> None:
        selected = table.selection()
        if selected:
            show_diagnostics(selected[0])

    table.bind("<<TreeviewSelect>>", on_select)

    def run() -> None:
        set_running(True)
        try:
            status_var.set("Получение исторических данных…")
            response = app.client.get_candles(str(detail["instrument_uid"]), interval="CANDLE_INTERVAL_DAY", days=2400)
            candles = _parse_candles(response)
            if len(candles) < 150:
                raise RuntimeError(f"Получено недостаточно свечей: {len(candles)}")
            status_var.set(f"Выполнение анализа: {len(candles)} свечей…")
            settings = ApplicationSettingsStore().load()
            store = SQLiteStore(settings.storage_path)
            service = AnalysisService(store)
            result = service.analyze(instrument_uid=str(detail["instrument_uid"]), ticker=str(detail.get("ticker", "")), candles=candles, profile=profile_var.get())
            position = _position_context(app, str(detail["instrument_uid"]))
            winner = next((item for item in result.strategies if item.quality_gate), None)
            opportunity = OpportunityEngine.evaluate(result, candles, winner)
            decision = DecisionEngine.evaluate(DecisionRequest(scenario=Scenario.SINGLE_INSTRUMENT, position=position, opportunity=opportunity.context, strategy_score=winner.score if winner else 0.0, strategy_name=winner.strategy if winner else None, strategy_quality=bool(winner), portfolio_allows_add=False, exit_signal=False, profile=profile_var.get()))
            run_id = service.save(result)
            AnalysisSnapshotRepository(store).save(result, run_id, decision)
            app.after(0, lambda result=result, candles=candles, position=position: (set_running(False), status_var.set("Анализ и Decision Engine завершены и сохранены"), set_result(result, candles, position)))
        except Exception as exc:
            error_text = str(exc)
            app.after(0, lambda error_text=error_text: (set_running(False), status_var.set("Ошибка анализа"), messagebox.showerror("Анализ акции", error_text, parent=window)))

    start_button.configure(command=lambda: threading.Thread(target=run, daemon=True).start())
