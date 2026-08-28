from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from edward.api.candles_client_patch import install as install_candles_client
from edward.config.application_settings import ApplicationSettingsStore
from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08
from edward.services.analysis_service import AnalysisService
from edward.services.decision_engine import DecisionEngine
from edward.storage.sqlite_store import SQLiteStore


def install(app_class: type[Any], client_class: type[Any]) -> None:
    import edward.ui.analysis_ui_v04 as legacy

    if getattr(app_class, "_analysis_ui_v08_installed", False):
        return
    install_candles_client(client_class)
    legacy._open_analysis = _open_analysis_v08
    app_class._analysis_ui_v08_installed = True


def _open_analysis_v08(app: Any) -> None:
    import edward.ui.analysis_ui_v04 as legacy

    detail = getattr(app, "instrument_detail", None)
    if not detail:
        return

    window = tk.Toplevel(app)
    window.title(f"Анализ акции v0.8 — {detail.get('ticker', '')}")
    window.geometry("1250x860")
    window.minsize(1100, 740)
    window.transient(app)

    top = ttk.Frame(window, padding=16)
    top.pack(fill="x")
    ttk.Label(top, text=f"Анализ: {detail.get('ticker', '')}", style="Title.TLabel").pack(side="left")
    ttk.Label(top, text="v0.8", font=("TkDefaultFont", 11, "bold")).pack(side="left", padx=(12, 0))
    profile_var = tk.StringVar(value="medium_term")
    ttk.Label(top, text="Профиль:").pack(side="left", padx=(28, 6))
    ttk.Combobox(top, textvariable=profile_var, state="readonly", values=("long_term", "medium_term", "speculative"), width=16).pack(side="left")
    status_var = tk.StringVar(value="Готов к запуску")
    ttk.Label(top, textvariable=status_var).pack(side="left", padx=(24, 0))
    progress = ttk.Progressbar(top, mode="indeterminate", length=180)
    progress.pack(side="left", padx=(12, 0))
    start_button = ttk.Button(top, text="Запустить анализ")
    start_button.pack(side="right")

    table = ttk.Treeview(window, columns=("strategy", "score", "return", "dd", "sharpe", "robust", "wf", "gate"), show="headings", height=11)
    for key, label, width in (
        ("strategy", "Стратегия", 180), ("score", "Score", 80), ("return", "OOS Return %", 105),
        ("dd", "OOS DD %", 95), ("sharpe", "Sharpe", 80), ("robust", "Robustness", 105),
        ("wf", "WF окон", 80), ("gate", "Quality Gate", 120),
    ):
        table.heading(key, text=label)
        table.column(key, width=width, anchor="center")
    table.pack(fill="both", expand=True, padx=16, pady=10)

    metrics = ttk.LabelFrame(window, text="v0.8 — Expected Value / Forecast / Portfolio", padding=12)
    metrics.pack(fill="x", padx=16, pady=(0, 10))
    for column in range(4):
        metrics.columnconfigure(column, weight=1)
    metric_vars = {key: tk.StringVar(value="—") for key in ("ev", "prob", "loss", "dist", "forecast", "regime", "portfolio", "confidence")}
    for index, (key, title) in enumerate((
        ("ev", "Expected Value"), ("prob", "P(profit)"), ("loss", "Expected Loss"), ("dist", "P10 → P90"),
        ("forecast", "Forecast Quality"), ("regime", "Regime"), ("portfolio", "Portfolio Impact"), ("confidence", "Confidence"),
    )):
        row, col = divmod(index, 4)
        cell = ttk.Frame(metrics, padding=6)
        cell.grid(row=row, column=col, sticky="nsew")
        ttk.Label(cell, text=title).pack(anchor="w")
        ttk.Label(cell, textvariable=metric_vars[key], font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(3, 0))

    decision_frame = ttk.LabelFrame(window, text="Торговое решение", padding=10)
    decision_frame.pack(fill="x", padx=16, pady=(0, 10))
    decision_var = tk.StringVar(value="Решение: —")
    reason_var = tk.StringVar(value="")
    ttk.Label(decision_frame, textvariable=decision_var, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(decision_frame, textvariable=reason_var, wraplength=1150, justify="left").pack(anchor="w", pady=(4, 0))

    explanation = tk.Text(window, height=7, wrap="word")
    explanation.pack(fill="x", padx=16, pady=(0, 16))
    explanation.configure(state="disabled")

    def running(value: bool) -> None:
        start_button.configure(state="disabled" if value else "normal")
        if value:
            progress.start(12)
        else:
            progress.stop()

    def set_metric(key: str, value: Any, suffix: str = "") -> None:
        if value is None:
            metric_vars[key].set("N/A")
        elif isinstance(value, str):
            metric_vars[key].set(value)
        else:
            metric_vars[key].set(f"{value}{suffix}")

    def show_result(pipeline_result: Any) -> None:
        result = pipeline_result.analysis
        for row in table.get_children():
            table.delete(row)
        for item in result.strategies:
            table.insert("", "end", values=(item.strategy, f"{item.score:.1f}", f"{item.return_pct:.2f}", f"{item.max_drawdown_pct:.2f}", f"{item.sharpe:.2f}", f"{item.stability:.1f}", item.wf_windows, "PASS" if item.quality_gate else "FAIL"))

        ev = pipeline_result.expected_value
        if ev.available:
            metric_vars["ev"].set(f"{ev.expected_value_pct:+.2f}%")
            metric_vars["prob"].set(f"{ev.probability_profit_pct:.1f}%")
            metric_vars["loss"].set(f"-{ev.expected_loss_pct:.2f}%")
            metric_vars["dist"].set(f"{ev.p10_pct:+.2f}% → {ev.p90_pct:+.2f}%")
            metric_vars["confidence"].set(ev.confidence)
        else:
            reason = ev.unavailable_reason or "данных недостаточно"
            for key in ("ev", "prob", "loss", "dist"):
                metric_vars[key].set("N/A")
            metric_vars["confidence"].set("N/A")

        if pipeline_result.forecast_quality_score is not None:
            metric_vars["forecast"].set(f"{pipeline_result.forecast_quality_score:.1f}")
        else:
            metric_vars["forecast"].set("N/A")

        regime_text = result.market_regime
        if pipeline_result.regime_confidence is not None:
            regime_text += f" ({pipeline_result.regime_confidence:.0f}%)"
        metric_vars["regime"].set(regime_text)

        if pipeline_result.portfolio_context_available:
            metric_vars["portfolio"].set(f"{pipeline_result.portfolio_impact.portfolio_impact_score:.1f}")
        else:
            metric_vars["portfolio"].set("N/A")

        winner = next((item for item in result.strategies if item.quality_gate), None)
        position = legacy._position_context(app, str(detail.get("instrument_uid", "")))
        request = legacy._build_decision_request(app, detail, result, pipeline_result.opportunity, winner, position, profile_var.get())
        decision = DecisionEngine.evaluate(request)
        decision_var.set(f"Решение: {decision.decision.value if decision.decision else '—'}")
        reason_var.set(decision.explanation)

        explanation.configure(state="normal")
        explanation.delete("1.0", "end")
        ev_note = "EV: недоступен — нет реализованных исходов." if not ev.available else f"EV: {ev.expected_value_pct:+.2f}% на {ev.observations} наблюдениях."
        portfolio_note = "Portfolio Impact: N/A — портфельный контекст не передан." if not pipeline_result.portfolio_context_available else f"Portfolio Impact: {pipeline_result.portfolio_impact.portfolio_impact_score:.1f}."
        explanation.insert("1.0", pipeline_result.opportunity.explanation + "\n\n" + result.explanation + f"\n\n{ev_note} {portfolio_note}")
        explanation.configure(state="disabled")

    def run() -> None:
        running(True)
        try:
            status_var.set("Получение исторических данных…")
            response = app.client.get_candles(str(detail["instrument_uid"]), interval="CANDLE_INTERVAL_DAY", days=2400)
            candles = legacy._parse_candles(response)
            if not candles:
                raise RuntimeError("Исторические свечи не получены")
            status_var.set(f"v0.8 анализ: {len(candles)} свечей…")
            pipeline = AnalysisPipelineServiceV08()
            result = pipeline.analyze(
                instrument_uid=str(detail["instrument_uid"]),
                ticker=str(detail.get("ticker", "")),
                candles=candles,
                profile=profile_var.get(),
            )
            settings = ApplicationSettingsStore().load()
            store = SQLiteStore(settings.storage_path)
            AnalysisService(store).save(result.analysis)
            app.after(0, lambda result=result: (running(False), status_var.set("v0.8 анализ завершён"), show_result(result)))
        except Exception as exc:
            text = str(exc)
            app.after(0, lambda text=text: (running(False), status_var.set("Ошибка анализа"), messagebox.showerror("Анализ v0.8", text, parent=window)))

    start_button.configure(command=lambda: threading.Thread(target=run, daemon=True).start())
    window.focus_force()


__all__ = ["install"]
