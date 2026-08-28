from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from edward.api.candles_client_patch import install as install_candles_client
from edward.config.application_settings import ApplicationSettingsStore
from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08
from edward.services.analysis_service import AnalysisService
from edward.services.decision_engine import Decision
from edward.services.decision_policy_v08 import DecisionPolicyV08
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
    for column in range(5):
        metrics.columnconfigure(column, weight=1)
    metric_vars = {key: tk.StringVar(value="—") for key in (
        "ev", "prob", "avg_win", "avg_loss", "pf", "forecast", "regime", "portfolio", "confidence", "observations"
    )}
    for index, (key, title) in enumerate((
        ("ev", "Expected Value"), ("prob", "P(profit)"), ("avg_win", "Avg Win"), ("avg_loss", "Avg Loss"), ("pf", "Profit Factor"),
        ("forecast", "Forecast Quality"), ("regime", "Regime"), ("portfolio", "Portfolio Impact"), ("confidence", "Confidence"), ("observations", "Наблюдения"),
    )):
        row, col = divmod(index, 5)
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

    policy = DecisionPolicyV08(
        buy_threshold=70.0 if profile_var.get() != "speculative" else 65.0,
        add_threshold=75.0 if profile_var.get() != "speculative" else 70.0,
        wait_threshold=45.0 if profile_var.get() != "speculative" else 40.0,
    )

    def running(value: bool) -> None:
        start_button.configure(state="disabled" if value else "normal")
        if value:
            progress.start(12)
        else:
            progress.stop()

    def show_result(pipeline_result: Any) -> None:
        result = pipeline_result.analysis
        for row in table.get_children():
            table.delete(row)
        for item in result.strategies:
            table.insert("", "end", values=(item.strategy, f"{item.score:.1f}", f"{item.return_pct:.2f}", f"{item.max_drawdown_pct:.2f}", f"{item.sharpe:.2f}", f"{item.stability:.1f}", item.wf_windows, "PASS" if item.quality_gate else "FAIL"))

        ev = pipeline_result.expected_value
        confidence = pipeline_result.confidence
        if ev.available:
            metric_vars["ev"].set(f"{ev.expected_value_pct:+.2f}%")
            metric_vars["prob"].set(f"{ev.probability_profit_pct:.1f}%")
            metric_vars["avg_win"].set(f"+{ev.average_win_pct:.2f}%" if ev.average_win_pct else "N/A")
            metric_vars["avg_loss"].set(f"-{ev.average_loss_pct:.2f}%" if ev.average_loss_pct else "N/A")
            denominator = ev.probability_loss_pct * ev.average_loss_pct
            numerator = ev.probability_profit_pct * ev.average_win_pct
            metric_vars["pf"].set("∞" if denominator == 0 and numerator > 0 else (f"{numerator / denominator:.2f}" if denominator > 0 else "N/A"))
            metric_vars["observations"].set(str(ev.observations))
        else:
            for key in ("ev", "prob", "avg_win", "avg_loss", "pf", "observations"):
                metric_vars[key].set("N/A")

        metric_vars["forecast"].set("N/A" if pipeline_result.forecast_quality_score is None else f"{pipeline_result.forecast_quality_score:.1f}")
        regime_text = result.market_regime
        if pipeline_result.regime_confidence is not None:
            regime_text += f" (confidence {pipeline_result.regime_confidence:.0f}%)"
        metric_vars["regime"].set(regime_text)
        metric_vars["portfolio"].set(f"{pipeline_result.portfolio_impact.portfolio_impact_score:.1f}" if pipeline_result.portfolio_context_available else "N/A")
        metric_vars["confidence"].set((f"{confidence.overall_confidence:.1f} — {confidence.level}") if confidence is not None else "N/A")

        position = legacy._position_context(app, str(detail.get("instrument_uid", "")))
        strategy_item = next((item for item in result.strategies if item.strategy == pipeline_result.evidence_strategy), None)
        market_ok = pipeline_result.opportunity.context.market_regime_compatible
        risk_ok = pipeline_result.opportunity.context.risk_ok
        entry_ok = pipeline_result.opportunity.context.entry_ok
        critical_risk = pipeline_result.opportunity.context.critical_risk
        confidence_score = confidence.overall_confidence if confidence is not None else 0.0

        if not position.is_open:
            decision_result = policy.evaluate_new_position(
                strategy=strategy_item,
                expected_value=ev,
                opportunity=pipeline_result.opportunity,
                confidence_score=confidence_score,
                entry_ok=entry_ok,
                market_ok=market_ok,
                risk_ok=risk_ok,
                critical_risk=critical_risk,
            )
        else:
            decision_result = policy.evaluate_existing_position(
                strategy=strategy_item,
                expected_value=ev,
                opportunity=pipeline_result.opportunity,
                confidence_score=confidence_score,
                entry_ok=entry_ok,
                market_ok=market_ok,
                risk_ok=risk_ok,
                critical_risk=critical_risk,
                exit_signal=bool(getattr(strategy_item, "exit_signal", False)) if strategy_item is not None else False,
            )
        decision = decision_result.decision or Decision.PASS
        reason = decision_result.explanation

        decision_var.set(f"Решение: {decision.value}")
        reason_var.set(reason)
        explanation.configure(state="normal")
        explanation.delete("1.0", "end")
        evidence = pipeline_result.evidence_strategy or "N/A"
        strategy_score = strategy_item.score if strategy_item is not None else None
        risk_score = getattr(getattr(pipeline_result.opportunity, "risk", None), "score", None)
        ci_text = (
            f"Historical EV 95% CI: {ev.ev_ci_low_pct:+.2f}% → {ev.ev_ci_high_pct:+.2f}%"
            if ev.available and ev.ev_ci_low_pct is not None and ev.ev_ci_high_pct is not None
            else "Historical EV 95% CI: N/A"
        )
        reliability_text = (
            f"Edge Reliability: {ev.edge_reliability_pct:.1f}% — {ev.edge_reliability_level}"
            if ev.available and ev.edge_reliability_pct is not None
            else "Edge Reliability: N/A"
        )
        lines = [
            f"Evidence strategy: {evidence}",
            f"Strategy score: {strategy_score:.1f}" if strategy_score is not None else "Strategy score: N/A",
            f"Robustness: {strategy_item.stability:.1f}" if strategy_item is not None else "Robustness: N/A",
            f"Regime: {result.market_regime}; regime confidence: {pipeline_result.regime_confidence:.1f}%" if pipeline_result.regime_confidence is not None else f"Regime: {result.market_regime}; regime confidence: N/A",
            f"Risk score: {risk_score:.1f}" if risk_score is not None else "Risk score: N/A",
            f"EV: {ev.expected_value_pct:+.2f}% across {ev.observations} realized outcomes" if ev.available else "EV: N/A — no realized outcomes",
            f"Avg Win: {ev.average_win_pct:+.2f}%; Avg Loss: -{ev.average_loss_pct:.2f}%" if ev.available else "Avg Win/Loss: N/A",
            ci_text,
            reliability_text,
            f"Portfolio Impact: {pipeline_result.portfolio_impact.portfolio_impact_score:.1f}" if pipeline_result.portfolio_context_available else "Portfolio Impact: N/A — portfolio context was not supplied",
            f"Confidence: {confidence.overall_confidence:.1f} ({confidence.level})" if confidence is not None else "Confidence: N/A",
            f"Decision: {decision.value} — {reason}",
        ]
        explanation.insert("1.0", "\n".join(lines))
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
            result = pipeline.analyze(instrument_uid=str(detail["instrument_uid"]), ticker=str(detail.get("ticker", "")), candles=candles, profile=profile_var.get())
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
